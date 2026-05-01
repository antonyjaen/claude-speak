"""Install claude-voice:* slash commands into ~/.claude/commands/."""
from __future__ import annotations

from pathlib import Path

COMMANDS_DIR = Path.home() / ".claude" / "commands"

_TEMPLATE = """---
description: {description}
allowed-tools: Bash(claude-voice:*)
---

Run this exact shell command and reply with one short line summarizing the
result. Do not add commentary.

```bash
{command}
```
"""

# (filename-stem, description, shell-command)
_COMMANDS = [
    ("claude-voice:shh", "Silence voice immediately (stop any TTS playing)",
     "claude-voice stop"),
    ("claude-voice:mode", "Toggle speak mode: end ↔ narrate",
     "claude-voice mode"),
    ("claude-voice:speaker-full", "Speak Claude's full reply when no Speaker line is present",
     "claude-voice config set speaker_only false"),
    ("claude-voice:speaker-only", "Only speak Claude's '🔊 Speaker:' line (silent if missing)",
     "claude-voice config set speaker_only true"),
    ("claude-voice:narrate", "Enable narrate mode — Claude speaks each step while working",
     "claude-voice install-interview"),
    ("claude-voice:narrate-stop", "Disable narrate mode — Claude speaks only at the end",
     "claude-voice uninstall-interview"),
    ("claude-voice:uninstall", "Remove all claude-voice hooks from settings",
     "claude-voice uninstall"),
    ("claude-voice:config", "Print every claude-voice setting and where it's coming from",
     "claude-voice config show"),
    ("claude-voice:help", "List every voice slash command with a short description",
     "claude-voice voice-help"),
]


def install_slash_commands() -> list[Path]:
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    known = {f"{name}.md" for name, _, _ in _COMMANDS}
    for stale in COMMANDS_DIR.glob("*.md"):
        is_old = (
            stale.name.startswith("voice-")
            or stale.name in ("shh.md", "mode.md")
            or stale.name.startswith("claude-voice:")
        )
        if is_old and stale.name not in known:
            stale.unlink(missing_ok=True)
    written: list[Path] = []
    for name, desc, cmd in _COMMANDS:
        p = COMMANDS_DIR / f"{name}.md"
        p.write_text(_TEMPLATE.format(description=desc, command=cmd), encoding="utf-8")
        written.append(p)
    return written
