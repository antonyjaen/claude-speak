<p align="center">
  <img src="icon/banner.svg" alt="claude-speak — TTS for Claude Code" width="800"/>
</p>

Hear every Claude Code reply without lifting a finger. Installs as a [Claude Code hook](https://docs.anthropic.com/en/docs/claude-code/hooks) — no API keys, no config required.

```
Claude picks up a tool  →  "Reading the config…"  spoken aloud
Claude picks up a tool  →  "Running the tests…"   spoken aloud
Claude finishes         →  full reply              spoken aloud
```

**Recommended mode: `narrate`** — voices each tool call as Claude works, then speaks the final reply. You always know what Claude is doing without looking at the screen.

**Default backend:** Microsoft Edge TTS (free, neural, online). Swap to `system` for fully offline playback (Windows SAPI / macOS `say` / Linux `espeak-ng`).

---

## Install

```bash
# 1. Install the package
pipx install claude-speak

# 2. Register hooks in ~/.claude/settings.json
claude-speak install-interview   # recommended: narrate tool calls + speak final reply
# claude-speak install           # minimal: speak final reply only
```

> **Python ≥ 3.9** required. `pipx` keeps it isolated — `pip install claude-speak` also works.

### Install via Claude prompt

Paste this into any Claude Code session and Claude will install and wire everything up for you:

```
Install claude-speak so you speak every tool call and final reply aloud.
Run: pipx install claude-speak && claude-speak install-interview
```

### Platform notes

| Platform | Notes |
|---|---|
| **Windows** | Works out of the box. Edge TTS recommended (better quality than SAPI). |
| **macOS** | Works out of the box. Uses `say` in system mode. |
| **Linux** | Install `espeak-ng` for system mode: `sudo apt install espeak-ng`. Edge TTS works on all distros. |

---

## How it works

Two hooks wire into Claude Code's event system:

- **PreToolUse** — fires before each tool call, speaks a short description of what Claude is about to do ("Searching for config files…", "Running tests…")
- **Stop** — fires at the end of every turn, speaks the full final reply after stripping code blocks and markdown

Three speaking modes control what gets spoken:

| Mode | What's spoken | How to enable |
|---|---|---|
| `narrate` ✦ recommended | Tool calls narrated live, then the final reply | `claude-speak install-interview` |
| `end` | The full final response only | `claude-speak install` |
| `end` + speaker-only | Only the `🔊 Speaker:` line if present | `claude-speak install-speaker` |

---

## Slash commands

Type these directly in the Claude Code prompt:

| Command | What it does |
|---|---|
| `/claude-speak:shh` | Stop speaking immediately |
| `/claude-speak:mode` | Toggle between `end` and `narrate` |
| `/claude-speak:speaker-only` | Speak only the `🔊 Speaker:` summary line |
| `/claude-speak:speaker-full` | Speak the full response (default) |
| `/claude-speak:narrate` | Enable narrate mode (speaks while working) |
| `/claude-speak:narrate-stop` | Disable narrate mode |
| `/claude-speak:config` | Show current configuration |
| `/claude-speak:help` | Show help text |
| `/claude-speak:lang-en` | Switch TTS voice to English |
| `/claude-speak:lang-es` | Switch TTS voice to Spanish |
| `/claude-speak:uninstall` | Remove all hooks and slash commands |

---

## CLI reference

```bash
claude-speak install            # register Stop hook
claude-speak install-speaker    # register Speaker-line extraction
claude-speak install-interview  # register narrate (PreToolUse) hook
claude-speak uninstall          # remove all hooks
claude-speak uninstall-interview

claude-speak speak "hello"      # one-shot TTS test
claude-speak voices             # list available voices
claude-speak config show        # show all settings
claude-speak config set <key> <value>
claude-speak mode               # toggle end ↔ narrate
claude-speak stop               # stop current playback

claude-speak hook stop          # (internal) called by Claude Code Stop hook
claude-speak hook pre-tool      # (internal) called by Claude Code PreToolUse hook
```

---

## Configuration

All settings can be overridden with environment variables or set persistently:

```bash
claude-speak config set voice_en en-GB-SoniaNeural
claude-speak config set speak_mode narrate
claude-speak config set max_chars 800
```

| Key | Env var | Default | Description |
|---|---|---|---|
| `lang` | `CLAUDE_SPEAK_LANG` | `en` | `en` · `es` — voice language |
| `speak_mode` | `CLAUDE_SPEAK_SPEAK_MODE` | `end` | `end` · `narrate` |
| `speaker_only` | `CLAUDE_SPEAK_SPEAKER_ONLY` | `false` | Speak only the `🔊 Speaker:` line |
| `backend` | `CLAUDE_SPEAK_BACKEND` | `edge` | `edge` (online) · `system` (offline) |
| `voice` | `CLAUDE_SPEAK_VOICE` | _(unset)_ | Override both EN and ES voices |
| `voice_en` | `CLAUDE_SPEAK_VOICE_EN` | `en-US-AriaNeural` | English voice |
| `voice_es` | `CLAUDE_SPEAK_VOICE_ES` | `es-MX-DaliaNeural` | Spanish voice |
| `rate` | `CLAUDE_SPEAK_RATE` | `0` | Speed offset: Edge uses percent (`-50`..`100`) |
| `max_chars` | `CLAUDE_SPEAK_MAX_CHARS` | `1200` | Truncate responses longer than this |
| `wake_word` | `CLAUDE_SPEAK_WAKE_WORD` | _(unset)_ | Require this phrase before speaking |
| `focus_pattern` | `CLAUDE_SPEAK_FOCUS_PATTERN` | _(unset)_ | Regex — only speak if active window matches |

---

## Voices

List all available Edge voices:

```bash
claude-speak voices
```

Set your preferred voice:

```bash
claude-speak config set voice_en en-GB-RyanNeural    # British male
claude-speak config set voice_es es-ES-ElviraNeural  # Spain Spanish female
```

Switch language with a slash command (default: English):

```bash
/claude-speak:lang-en   # switch to English voice
/claude-speak:lang-es   # switch to Spanish voice
```

Set `voice` (not `voice_en`/`voice_es`) to force a single voice regardless of language.

---

## Status line

Add the current mode to your Claude Code status bar:

```bash
claude-speak install-statusline
```

Shows `🔊 end`, `🔊 narrate`, or `🔇 off` depending on active hooks.

---

## Diagnostics

```bash
claude-speak doctor
```

Checks: Python version, `pygame` playback, Edge TTS connectivity, hooks registered in `~/.claude/settings.json`, slash commands installed.

---

## Uninstall

```bash
# Remove hooks + slash commands (keeps package installed)
claude-speak uninstall

# Remove the package entirely
pipx uninstall claude-speak
```

---

## License

MIT
