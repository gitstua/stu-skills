#!/usr/bin/env python3
"""Parse .ics (iCalendar) files and emit normalized event data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


DATE_RE = re.compile(r"^\d{8}$")
DATETIME_RE = re.compile(r"^\d{8}T\d{6}Z?$")


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


def format_local_datetime(value: object, all_day: bool = False) -> Optional[str]:
    if not isinstance(value, str):
        return None

    try:
        local_tz = dt.datetime.now().astimezone().tzinfo
        if len(value) == 10:
            d = dt.date.fromisoformat(value)
            if all_day:
                return f"{d.strftime('%a')} {d.day} {d.strftime('%b')} (all day)"
            local_dt = dt.datetime.combine(d, dt.time.min).replace(tzinfo=local_tz)
            return f"{local_dt.strftime('%a')} {local_dt.day} {local_dt.strftime('%b %H:%M')}"

        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=local_tz)
        local_dt = parsed.astimezone(local_tz)
        return f"{local_dt.strftime('%a')} {local_dt.day} {local_dt.strftime('%b %H:%M')}"
    except Exception:
        return value


def filter_events(
    events: List[Dict[str, object]],
    after: Optional[dt.datetime],
    before: Optional[dt.datetime],
    limit: Optional[int],
) -> List[Dict[str, object]]:
    annotated: List[Tuple[dt.datetime, Dict[str, object]]] = []
    for event in events:
        start = normalize_event_start(event)
        if start is None:
            continue
        if after and start < after:
            continue
        if before and start > before:
            continue
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


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    load_env_defaults(skill_root)

    parser = argparse.ArgumentParser(description="Parse iCalendar (.ics) events")
    parser.add_argument("ics_path", nargs="?", help="Path to .ics file")
    parser.add_argument(
        "--url",
        action="append",
        help="HTTPS iCal URL to fetch (repeatable or comma-separated)",
    )
    parser.add_argument("--after", help="ISO datetime or 'now'")
    parser.add_argument("--before", help="ISO datetime")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    raw_url_inputs: List[str] = args.url or []
    if not raw_url_inputs:
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
            "(comma-separated), or pass --url/ics_path.\n"
            "Ask the user to provide ICS_URLS for this session.",
            file=sys.stderr,
        )
        return 2

    events: List[Dict[str, object]] = []
    if args.ics_path:
        content = Path(args.ics_path).read_text(encoding="utf-8", errors="replace")
        events.extend(parse_ics_events(content))

    for url in urls:
        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8", errors="replace")
        events.extend(parse_ics_events(content))

    after = parse_filter_dt(args.after) if args.after else None
    before = parse_filter_dt(args.before) if args.before else None
    filtered = filter_events(events, after=after, before=before, limit=args.limit)

    if args.format == "json":
        print(json.dumps(filtered, indent=2, ensure_ascii=False))
    else:
        print(render_text(filtered))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
