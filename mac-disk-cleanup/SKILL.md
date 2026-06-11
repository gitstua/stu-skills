---
name: mac-disk-cleanup
description: Free disk space on macOS by cleaning dev caches (npm, pip, uv, Homebrew) and removing stale node_modules from old projects. Use this skill whenever the user mentions disk space, storage full, Mac running out of space, cleaning up node_modules, or wants to free space on their Mac — even if they don't say "cleanup" explicitly.
---

# Mac Disk Cleanup

Two-part workflow: safe cache cleanup, then stale node_modules removal.

## Part 1 — Cache cleanup (always safe, no user decision needed)

Run `scripts/clean_caches.sh`. This clears:
- npm cache (`~/.npm`)
- pip3 cache (`~/Library/Caches/pip`)
- uv cache (`~/.cache/uv`)
- Homebrew old versions + downloads cache

Report MB freed per tool.

## Part 2 — node_modules audit and cleanup

### Find candidates

Run `scripts/find_node_modules.sh` (optionally pass a root dir, defaults to `$HOME`).

Output is tab-separated: `size_mb  last_modified_date  path`

### Classify by staleness

Use the parent directory's last-modified date to judge staleness:

| Age | Action |
|-----|--------|
| Last modified > 6 months ago | Safe to remove — offer to clean automatically |
| Last modified 1–6 months ago | Ask the user before removing |
| Last modified < 1 month ago | Leave alone (skip) |
| Path contains `/Downloads/` | Always remove — these are stale copies |
| Path contains `/old/` or `/archive/` | Always remove |
| Path is the current working directory | Always skip |

### Skip managed directories

These are already excluded by the script, but double-check you never delete from:
- `~/.nvm/` — node version manager (removing breaks node)
- `~/.vscode/extensions/` — VS Code manages these
- `~/.copilot/`, `~/.lmstudio/`, `~/.cache/opencode/` — tool-managed

### Clean and report

For the stale candidates, show the user the list with sizes before deleting. Then:

```bash
rm -rf "/path/to/node_modules"
```

Report total MB freed. Remind the user that `npm install` restores any removed `node_modules`.

## Part 3 — Disk summary

After cleanup, run:

```bash
df -h / | awk 'NR==2 {print "Free: "$4" / "$2" ("$5" used)"}'
```

Report the before/after free space.

## What NOT to touch

- Browser caches (Arc, Chrome, WhatsApp) — these rebuild automatically but clearing them requires quitting the app first; only do this if the user explicitly asks
- `~/Library/Application Support/` — app data, not cache
- Python virtual environments (`.venv/`, `venv/`) — don't delete these without asking
