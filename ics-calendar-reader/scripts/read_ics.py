#!/usr/bin/env python3
"""Parse .ics (iCalendar) files and emit normalized event data."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


DATE_RE = re.compile(r"^\d{8}$")
DATETIME_RE = re.compile(r"^\d{8}T\d{6}Z?$")
WEEKDAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_ABBR = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
DEFAULT_CACHE_TTL_SECONDS = 900


def parse_env_line(line: str) -> Optional[Tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if len(value) >= 2 and (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        value = value[1:-1]

    return key, value


def resolve_env_file_from_config(skill_root: Path) -> Optional[Path]:
    config_path = skill_root / ".env-path"
    if not config_path.exists():
        return None

    for raw_line in config_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        expanded = os.path.expanduser(line)
        env_path = Path(expanded)
        if env_path.exists():
            return env_path
        return None
    return None


def load_env_defaults(skill_root: Path) -> None:
    env_file = resolve_env_file_from_config(skill_root)
    if env_file is None:
        return

    for raw_line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def unfold_ical_lines(text: str) -> List[str]:
    """Join folded ICS lines (continuations start with space or tab)."""
    raw_lines = text.splitlines()
    unfolded: List[str] = []
    for line in raw_lines:
        if not unfolded:
            unfolded.append(line)
            continue
        if line.startswith(" ") or line.startswith("\t"):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def unescape_ical_text(value: str) -> str:
    return (
        value.replace("\\\\", "\\")
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
    )


def parse_property(line: str) -> Tuple[str, Dict[str, str], str]:
    left, _, value = line.partition(":")
    key_part, *param_parts = left.split(";")
    key = key_part.upper()
    params: Dict[str, str] = {}
    for part in param_parts:
        if "=" in part:
            pkey, pvalue = part.split("=", 1)
            params[pkey.upper()] = pvalue
    return key, params, value


def parse_dt(value: str, params: Dict[str, str]) -> Tuple[Optional[dt.datetime], Optional[str], bool]:
    """Return tuple: sortable_dt, ISO string, all_day."""
    value = value.strip()
    tzid = params.get("TZID")

    if DATE_RE.match(value):
        d = dt.datetime.strptime(value, "%Y%m%d").date()
        # Represent all-day at midnight local (naive), plus explicit all_day flag.
        as_dt = dt.datetime.combine(d, dt.time.min)
        return as_dt, d.isoformat(), True

    if DATETIME_RE.match(value):
        if value.endswith("Z"):
            parsed = dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=dt.timezone.utc
            )
            return parsed, parsed.isoformat(), False

        parsed = dt.datetime.strptime(value, "%Y%m%dT%H%M%S")
        if tzid and ZoneInfo is not None:
            try:
                parsed = parsed.replace(tzinfo=ZoneInfo(tzid))
            except Exception:
                pass
        return parsed, parsed.isoformat(), False

    return None, None, False


def parse_ics_events(text: str) -> List[Dict[str, object]]:
    lines = unfold_ical_lines(text)

    events: List[Dict[str, object]] = []
    current: Optional[Dict[str, object]] = None

    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {
                "summary": None,
                "start": None,
                "end": None,
                "all_day": False,
                "location": None,
                "description": None,
                "status": None,
                "uid": None,
                "organizer": None,
                "attendees": [],
                "_sort_start": None,
            }
            continue

        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue

        if current is None or ":" not in line:
            continue

        key, params, value = parse_property(line)
        raw_value = unescape_ical_text(value)

        if key == "SUMMARY":
            current["summary"] = raw_value
        elif key == "DESCRIPTION":
            current["description"] = raw_value
        elif key == "LOCATION":
            current["location"] = raw_value
        elif key == "STATUS":
            current["status"] = raw_value
        elif key == "UID":
            current["uid"] = raw_value
        elif key == "ORGANIZER":
            current["organizer"] = raw_value
        elif key == "ATTENDEE":
            cn = params.get("CN")
            attendee_value = raw_value
            if cn:
                attendee_value = f"{cn} <{raw_value}>"
            current["attendees"].append(attendee_value)
        elif key == "DTSTART":
            sort_dt, iso, all_day = parse_dt(raw_value, params)
            current["start"] = iso
            current["all_day"] = all_day
            current["_sort_start"] = sort_dt
        elif key == "DTEND":
            _, iso, _ = parse_dt(raw_value, params)
            current["end"] = iso

    for event in events:
        event.pop("_sort_start", None)

    return events


def parse_filter_dt(value: str) -> dt.datetime:
    if value.lower() == "now":
        return dt.datetime.now(dt.timezone.utc)
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def normalize_event_start(event: Dict[str, object]) -> Optional[dt.datetime]:
    start = event.get("start")
    if not isinstance(start, str):
        return None
    try:
        if len(start) == 10:
            d = dt.date.fromisoformat(start)
            return dt.datetime.combine(d, dt.time.min).replace(tzinfo=dt.timezone.utc)
        parsed = dt.datetime.fromisoformat(start)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def normalize_event_end(event: Dict[str, object]) -> Optional[dt.datetime]:
    end = event.get("end")
    if not isinstance(end, str):
        return normalize_event_start(event)
    try:
        if len(end) == 10:
            d = dt.date.fromisoformat(end)
            return dt.datetime.combine(d, dt.time.min).replace(tzinfo=dt.timezone.utc)
        parsed = dt.datetime.fromisoformat(end)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return normalize_event_start(event)


def format_local_datetime(value: object, all_day: bool = False) -> Optional[str]:
    if not isinstance(value, str):
        return None

    try:
        local_tz = dt.datetime.now().astimezone().tzinfo
        if len(value) == 10:
            d = dt.date.fromisoformat(value)
            weekday = WEEKDAY_ABBR[d.weekday()]
            month = MONTH_ABBR[d.month - 1]
            if all_day:
                return f"{weekday} {d.day} {month} {d.year} (all day)"
            local_dt = dt.datetime.combine(d, dt.time.min).replace(tzinfo=local_tz)
            weekday = WEEKDAY_ABBR[local_dt.weekday()]
            month = MONTH_ABBR[local_dt.month - 1]
            return f"{weekday} {local_dt.day} {month} {local_dt.year} {local_dt:%H:%M}"

        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=local_tz)
        local_dt = parsed.astimezone(local_tz)
        weekday = WEEKDAY_ABBR[local_dt.weekday()]
        month = MONTH_ABBR[local_dt.month - 1]
        return f"{weekday} {local_dt.day} {month} {local_dt.year} {local_dt:%H:%M}"
    except Exception:
        return value


def add_display_datetimes(events: List[Dict[str, object]]) -> List[Dict[str, object]]:
    for event in events:
        all_day = bool(event.get("all_day"))
        event["start_local"] = format_local_datetime(event.get("start"), all_day)
        event["end_local"] = format_local_datetime(event.get("end"), all_day)
    return events


def filter_events(
    events: List[Dict[str, object]],
    after: Optional[dt.datetime],
    before: Optional[dt.datetime],
    limit: Optional[int],
) -> List[Dict[str, object]]:
    annotated: List[Tuple[dt.datetime, Dict[str, object]]] = []
    now = dt.datetime.now(dt.timezone.utc)
    for event in events:
        start = normalize_event_start(event)
        end = normalize_event_end(event)
        if start is None or end is None:
            continue

        # Overlap filtering so long-running events are included.
        if after and end < after:
            continue
        if before and start > before:
            continue

        event["is_ongoing"] = start <= now <= end
        annotated.append((start, event))

    annotated.sort(key=lambda pair: pair[0])
    filtered = [event for _, event in annotated]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def render_text(events: List[Dict[str, object]]) -> str:
    if not events:
        return "No matching events."

    lines: List[str] = []
    for idx, event in enumerate(events, start=1):
        start_local = format_local_datetime(event.get("start"), bool(event.get("all_day")))
        end_local = format_local_datetime(event.get("end"), bool(event.get("all_day")))
        lines.append(f"{idx}. {event.get('summary') or '(no title)'}")
        lines.append(f"   start: {start_local}")
        lines.append(f"   end: {end_local}")
        lines.append(f"   all_day: {event.get('all_day')}")
        if event.get("location"):
            lines.append(f"   location: {event.get('location')}")
        if event.get("status"):
            lines.append(f"   status: {event.get('status')}")
        if event.get("organizer"):
            lines.append(f"   organizer: {event.get('organizer')}")
        attendees = event.get("attendees")
        if isinstance(attendees, list) and attendees:
            lines.append(f"   attendees: {', '.join(attendees)}")
    return "\n".join(lines)


def split_urls(values: List[str]) -> List[str]:
    urls: List[str] = []
    for value in values:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned:
                urls.append(cleaned)
    return urls


def normalize_calendar_url(url: str) -> str:
    """Normalize calendar URL schemes for urllib compatibility."""
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme == "webcal":
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    if scheme == "webcals":
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    return url


def default_cache_dir() -> Path:
    env_cache_dir = os.environ.get("ICS_CACHE_DIR")
    if env_cache_dir:
        return Path(os.path.expanduser(env_cache_dir))

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        base = Path(os.path.expanduser(xdg_cache_home))
    else:
        base = Path.home() / ".cache"
    return base / "stu-skills" / "ics-calendar-reader"


def url_cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def parse_cached_timestamp(value: object) -> Optional[dt.datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def fetch_ics_url_content(url: str, cache_dir: Path, cache_ttl: int) -> str:
    if cache_ttl <= 0:
        with urllib.request.urlopen(url) as response:
            return response.read().decode("utf-8", errors="replace")

    cache_dir.mkdir(parents=True, exist_ok=True)
    key = url_cache_key(url)
    body_path = cache_dir / f"{key}.ics"
    meta_path = cache_dir / f"{key}.json"

    meta: Dict[str, object] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    now = dt.datetime.now(dt.timezone.utc)
    fetched_at = parse_cached_timestamp(meta.get("fetched_at"))
    if body_path.exists() and fetched_at is not None:
        age_seconds = (now - fetched_at).total_seconds()
        if age_seconds <= cache_ttl:
            return body_path.read_text(encoding="utf-8", errors="replace")

    headers: Dict[str, str] = {}
    etag = meta.get("etag")
    last_modified = meta.get("last_modified")
    if isinstance(etag, str) and etag:
        headers["If-None-Match"] = etag
    if isinstance(last_modified, str) and last_modified:
        headers["If-Modified-Since"] = last_modified

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            content = response.read().decode("utf-8", errors="replace")
            body_path.write_text(content, encoding="utf-8")
            updated_meta = {
                "url": url,
                "fetched_at": now.isoformat(),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
            }
            meta_path.write_text(json.dumps(updated_meta, indent=2), encoding="utf-8")
            return content
    except urllib.error.HTTPError as exc:
        if exc.code == 304 and body_path.exists():
            meta["url"] = url
            meta["fetched_at"] = now.isoformat()
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            return body_path.read_text(encoding="utf-8", errors="replace")
        raise
    except Exception:
        if body_path.exists():
            print(
                f"Warning: fetch failed for {url}; using stale cached calendar content.",
                file=sys.stderr,
            )
            return body_path.read_text(encoding="utf-8", errors="replace")
        raise


def get_default_cache_ttl() -> int:
    raw = os.environ.get("ICS_CACHE_TTL_SECONDS")
    if raw is None:
        return DEFAULT_CACHE_TTL_SECONDS
    try:
        return max(int(raw), 0)
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    load_env_defaults(skill_root)
    configured_env_path = resolve_env_file_from_config(skill_root)

    parser = argparse.ArgumentParser(description="Parse iCalendar (.ics) events")
    parser.add_argument("ics_path", nargs="?", help="Path to .ics file")
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--after", help="ISO datetime or 'now'")
    parser.add_argument("--before", help="ISO datetime")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=get_default_cache_ttl(),
        help=(
            "Cache TTL in seconds for downloaded ICS URLs (default: 900). "
            "Set to 0 to disable cache."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for ICS URL cache files (default: XDG cache path).",
    )
    args = parser.parse_args()

    if args.url:
        env_hint = (
            str(configured_env_path)
            if configured_env_path is not None
            else "~/.config/stu-skills/ics-calendar-reader/.env"
        )
        print(
            "Refusing --url for privacy. Store calendar URLs in ICS_URLS via "
            f"{env_hint}, then run without --url.",
            file=sys.stderr,
        )
        return 2

    raw_url_inputs: List[str] = []
    env_urls = os.environ.get("ICS_URLS")
    if env_urls:
        raw_url_inputs.append(env_urls)
    elif os.environ.get("ICS_URL"):
        # Backward-compatible fallback for older setups.
        raw_url_inputs.append(os.environ["ICS_URL"])
    urls = split_urls(raw_url_inputs)

    if not args.ics_path and not urls:
        print(
            "Missing prerequisite: set ICS_URLS to one or more calendar URLs "
            "(comma-separated), or pass ics_path.\n"
            "Ask the user to provide ICS_URLS for this session.",
            file=sys.stderr,
        )
        return 2

    events: List[Dict[str, object]] = []
    if args.ics_path:
        content = Path(args.ics_path).read_text(encoding="utf-8", errors="replace")
        events.extend(parse_ics_events(content))

    cache_dir = Path(os.path.expanduser(args.cache_dir)) if args.cache_dir else default_cache_dir()
    cache_ttl = max(args.cache_ttl, 0)

    for url in urls:
        normalized_url = normalize_calendar_url(url)
        content = fetch_ics_url_content(
            normalized_url,
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
        )
        events.extend(parse_ics_events(content))

    after = parse_filter_dt(args.after) if args.after else None
    before = parse_filter_dt(args.before) if args.before else None
    filtered = filter_events(events, after=after, before=before, limit=args.limit)
    filtered = add_display_datetimes(filtered)

    if args.format == "json":
        print(json.dumps(filtered, indent=2, ensure_ascii=False))
    else:
        print(render_text(filtered))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
