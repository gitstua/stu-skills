---
name: ntfy-notify
description: Send push notifications via ntfy.sh with a lightweight shell workflow. Use when posting alerts, job status updates, reminders, or automation results to an ntfy topic using token auth or public topics.
license: GPL-3.0-only
---

# ntfy Notify

Use `scripts/ntfy_send.sh` for deterministic, low-overhead notifications.

## Prerequisites

- Required default topic: `NTFY_DEFAULT_TOPIC`
  - Example: `export NTFY_DEFAULT_TOPIC="my-topic"`
- Optional auth: `NTFY_ACCESS_TOKEN` (script also accepts legacy `NTFY_TOKEN`)
  - Example: `export NTFY_ACCESS_TOKEN="<your-ntfy-access-token>"`
- If `NTFY_DEFAULT_TOPIC` is missing and `--topic` is not passed, the script exits with an instruction for the agent to ask the user for it.

## Configure

1. Set a default topic:
   - `export NTFY_DEFAULT_TOPIC="my-topic"`
2. Optionally set token auth:
   - `export NTFY_ACCESS_TOKEN="<your-ntfy-access-token>"`
3. Optional custom server (default is `https://ntfy.sh`):
   - `export NTFY_SERVER="https://ntfy.sh"`

## Send

- Basic:
  - `scripts/ntfy_send.sh "Build finished"`
- Explicit topic:
  - `scripts/ntfy_send.sh --topic ops-alerts "Backup completed"`
- Add title/priority/tags:
  - `scripts/ntfy_send.sh --title "Deploy" --priority 4 --tags rocket,white_check_mark "Release shipped"`

## Notes

- Prefer env vars for secrets and defaults.
- Keep messages short and actionable.
- Use `--dry-run` to verify payload/header behavior without network calls.
