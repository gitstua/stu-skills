---
name: ics-calendar-reader
description: Read, parse, and summarize iCalendar (.ics) files from Google Calendar, Apple Calendar, and similar providers. Use when extracting upcoming events, filtering by date range, converting ICS events to JSON/text, or debugging calendar fields like DTSTART/DTEND/TZID/RRULE.
license: GPL-3.0-only
---

# ICS Calendar Reader

Parse `.ics` files with `scripts/read_ics.py` instead of hand-parsing text.

## Prerequisite

- Set `ICS_URLS` to one or more calendar URLs (comma-separated).
  - Example: `export ICS_URLS="https://example.com/a.ics,https://example.com/b.ics"`
- Secrets/defaults file: `~/.config/stu-skills/ics-calendar-reader/.env`
  - The script reads this path from `ics-calendar-reader/.env-path` automatically.
- If `ICS_URLS` is missing and no `--url`/`ics_path` is provided, the script exits with an instruction for the agent to ask the user for it.

## .env Sample

Path: `~/.config/stu-skills/ics-calendar-reader/.env`

```dotenv
ICS_URLS="https://example.com/a.ics,https://example.com/b.ics"
```

## Workflow

1. Run the parser on the file and request JSON for reliable downstream use:
   - `python3 scripts/read_ics.py /path/to/calendar.ics --format json`
   - `python3 scripts/read_ics.py --url "https://example.com/calendar.ics" --format json`
2. Filter to upcoming events or a window:
   - `python3 scripts/read_ics.py /path/to/calendar.ics --after now --limit 20 --format json`
   - `python3 scripts/read_ics.py /path/to/calendar.ics --after 2026-02-01T00:00:00 --before 2026-03-01T00:00:00 --format json`
   - `ICS_URLS="https://example.com/calendar.ics,https://example.com/team.ics" python3 scripts/read_ics.py --after now --limit 20 --format json`
3. Use text output for quick human review:
   - `python3 scripts/read_ics.py /path/to/calendar.ics --format text`

## Output Contract

Expect each event to include:

- `summary`
- `start` (ISO-8601)
- `end` (ISO-8601 when available)
- `all_day` (boolean)
- `location`
- `description`
- `status`
- `uid`
- `organizer`
- `attendees`

## Notes

- Treat parsed JSON as source of truth for further transformations.
- Keep timezone-aware datetimes intact; do not strip offsets.
- For recurring events, treat each VEVENT record present in the file as one parsed item.
- If needed, read `references/ics-fields.md` for quick field semantics.
- For private calendar subscriptions, prefer storing URLs in `ICS_URLS` instead of pasting them repeatedly.
