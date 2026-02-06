# Stu Skills

A small collection of reusable agent skills with scripts and references.
Each skill lives in its own folder with a SKILL.md entry point.

## Skills

- ics-calendar-reader: Parse .ics calendars to JSON or text using scripts/read_ics.py.
- ntfy-notify: Send ntfy.sh notifications using scripts/ntfy_send.sh.

## Repo Layout

- <skill>/SKILL.md: The skill entry point and usage guidance.
- <skill>/scripts/: Supporting scripts for the skill.
- <skill>/references/: Optional references for the skill.

## Installation

These skills are plain Markdown with optional helper scripts. Any tool that
supports a custom skills directory can load them.

1) Pick a shared skills directory.

- Example: ~/.agents/skills

2) Copy the main skill folders into `~/.agents/skills` (recommended base setup).

3) Symlink tool-specific skill locations to `~/.agents/skills` (Claude, Gemini, Codexapp, Codex CLI, etc).

- Example pattern:
  - ln -s ~/.agents/skills ~/.claude/skills
  - ln -s ~/.agents/skills ~/.gemini/skills
  - ln -s ~/.agents/skills ~/.codexapp/skills
  - ln -s ~/.agents/skills ~/.codexcli/skills

4) Configure your tool to include that skills directory.

Most tools provide one of these options:
- A settings entry for skills/agents search paths
- A CLI flag or environment variable that points to the skills directory
- A custom instructions file that can reference or import SKILL.md

5) Verify.

Ask your tool to list available skills or explicitly load a skill by name.

Optional: If another tool expects a different default path, symlink that
location to `~/.agents/skills` using the same pattern above.

## Tool Notes

- Gemini, Claude, Codexapp, Codex CLI, and similar tools can use these skills
  as long as they are configured to read a skills directory or a set of
  instruction files. If your tool needs a specific config key, point it to the
  directory that contains the skill folders (for example, ~/.agents/skills).
- If a tool requires a single file, you can copy or merge the SKILL.md content
  into its custom instructions.

## License

GNU General Public License v3.0 only (GPL-3.0-only). See LICENSE.
