---
name: mac-disk-cleanup
description: Free disk space on macOS by cleaning dev caches (npm, pip, uv, Homebrew), removing stale node_modules from old projects, and optionally removing LM Studio or Ollama models after confirmation. Use this skill whenever the user mentions disk space, storage full, Mac running out of space, cleaning up node_modules, LM Studio models, Ollama models, or wants to free space on their Mac — even if they don't say "cleanup" explicitly.
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

## Part 2 — LM Studio / Ollama model cleanup (confirmation required)

These models are large files that can't be re-downloaded automatically — always confirm before deleting.

### LM Studio

List installed models with sizes:
```bash
find ~/.lmstudio/models -name "*.gguf" -o -name "*.safetensors" 2>/dev/null \
  | xargs du -sh 2>/dev/null | sort -rh
```

Show the list to the user and ask which models to remove. Delete by removing the model's parent folder (e.g. `~/.lmstudio/models/publisher/model-name/`) so stale metadata doesn't linger.

### Ollama

List installed models:
```bash
ollama list 2>/dev/null
```

For each model the user wants to remove:
```bash
ollama rm <model-name>
```

This is the correct removal method — do not delete `~/.ollama/models/blobs/` directly, as Ollama manages content-addressed storage there and manual deletion can corrupt the store.

### Confirmation rule

Always show a summary of what will be deleted and its total size, then ask: "OK to delete these models?" before proceeding. Never delete models without an explicit yes.

## Part 3 — node_modules audit and cleanup

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
- `~/.copilot/`, `~/.cache/opencode/` — tool-managed
- `~/.lmstudio/` outside of `models/` — app config, not models
- `~/.ollama/models/blobs/` — use `ollama rm` instead of direct deletion

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
