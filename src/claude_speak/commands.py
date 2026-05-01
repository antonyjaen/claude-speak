"""Install claude-speak:* slash commands into ~/.claude/commands/claude-speak/."""
from __future__ import annotations

from pathlib import Path

COMMANDS_DIR = Path.home() / ".claude" / "commands" / "claude-speak"

_TEMPLATE = """---
description: {description}
allowed-tools: Bash(claude-speak:*)
---

Run this exact shell command and reply with one short line summarizing the
result. Do not add commentary.

```bash
{command}
```
"""

# (filename-stem, description, shell-command)
_COMMANDS = [
    ("claude-speak:shh", "Silence voice immediately (stop any TTS playing)",
     "claude-speak stop"),
    ("claude-speak:mode", "Toggle speak mode: end ↔ narrate",
     "claude-speak mode"),
    ("claude-speak:speaker-full", "Speak Claude's full reply when no Speaker line is present",
     "claude-speak config set speaker_only false"),
    ("claude-speak:speaker-only", "Only speak Claude's '🔊 Speaker:' line (silent if missing)",
     "claude-speak config set speaker_only true"),
    ("claude-speak:narrate", "Enable narrate mode — Claude speaks each step while working",
     "claude-speak install-interview"),
    ("claude-speak:narrate-stop", "Disable narrate mode — Claude speaks only at the end",
     "claude-speak uninstall-interview"),
    ("claude-speak:lang-en", "Switch TTS language to English",
     "claude-speak config set lang en"),
    ("claude-speak:lang-es", "Switch TTS language to Spanish",
     "claude-speak config set lang es"),
    ("claude-speak:uninstall", "Remove all claude-speak hooks from settings",
     "claude-speak uninstall"),
    ("claude-speak:config", "Print every claude-speak setting and where it's coming from",
     "claude-speak config show"),
    ("claude-speak:help", "List every voice slash command with a short description",
     "claude-speak voice-help"),
]


def install_slash_commands() -> list[Path]:
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove legacy flat files (pre-subdirectory layout, Windows-incompatible names)
    legacy_dir = COMMANDS_DIR.parent
    for stale in list(legacy_dir.glob("*.md")) + list(legacy_dir.iterdir()):
        if stale.is_file() and (
            stale.name.startswith("voice-")
            or stale.name in ("shh.md", "mode.md", "claude-voice")
            or stale.name.startswith("claude-speak")
        ):
            stale.unlink(missing_ok=True)

    written: list[Path] = []
    for name, desc, cmd in _COMMANDS:
        # name is "claude-speak:shh"; file lives in subdir as "shh.md"
        short = name.split(":", 1)[-1]
        p = COMMANDS_DIR / f"{short}.md"
        p.write_text(_TEMPLATE.format(description=desc, command=cmd), encoding="utf-8")
        written.append(p)
    return written
