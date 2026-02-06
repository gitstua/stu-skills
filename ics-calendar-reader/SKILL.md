---
name: ics-calendar-reader
description: Read, parse, and summarize iCalendar (.ics) files from Google Calendar, Apple Calendar, and similar providers. Use when extracting upcoming events, filtering by date range, converting ICS events to JSON/text, or debugging calendar fields like DTSTART/DTEND/TZID/RRULE.
---

# ICS Calendar Reader

Parse `.ics` files with `scripts/read_ics.py` instead of hand-parsing text.

## Workflow

1. Run the parser on the file and request JSON for reliable downstream use:
   - `python3 scripts/read_ics.py /path/to/calendar.ics --format json`
   - `python3 scripts/read_ics.py --url "https://example.com/calendar.ics" --format json`
2. Filter to upcoming events or a window:
   - `python3 scripts/read_ics.py /path/to/calendar.ics --after now --limit 20 --format json`
   - `python3 scripts/read_ics.py /path/to/calendar.ics --after 2026-02-01T00:00:00 --before 2026-03-01T00:00:00 --format json`
   - `ICS_URL="https://example.com/calendar.ics" python3 scripts/read_ics.py --after now --limit 20 --format json`
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
- For private calendar subscriptions, prefer storing the URL in `ICS_URL` instead of pasting it repeatedly.
