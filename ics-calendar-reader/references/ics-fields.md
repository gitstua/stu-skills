# ICS Field Notes

Common fields in Google/Apple exports:

- `DTSTART`: Event start.
- `DTEND`: Event end. Some all-day events may omit explicit end.
- `SUMMARY`: Title.
- `DESCRIPTION`: Body text, usually with escaped newlines.
- `LOCATION`: Location text.
- `UID`: Stable event identifier.
- `STATUS`: `CONFIRMED`, `TENTATIVE`, or `CANCELLED`.
- `ORGANIZER`: Event organizer (often `mailto:` URI).
- `ATTENDEE`: One attendee per line; may include params like `CN=`.
- `RRULE`: Recurrence rule metadata.
- `EXDATE`: Excluded recurrence dates.

Date/time patterns:

- UTC timestamp: `YYYYMMDDTHHMMSSZ`
- Local timestamp: `YYYYMMDDTHHMMSS` (may include `TZID`)
- All-day date: `YYYYMMDD`

Escaping:

- `\\n` => newline
- `\\,` => comma
- `\\;` => semicolon
- `\\\\` => backslash
