<p align="center">
  <img src="icon/banner.svg" alt="claude-voice — TTS for Claude Code" width="800"/>
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
pipx install claude-voice

# 2. Register hooks in ~/.claude/settings.json
claude-voice install-interview   # recommended: narrate tool calls + speak final reply
# claude-voice install           # minimal: speak final reply only
```

> **Python ≥ 3.9** required. `pipx` keeps it isolated — `pip install claude-voice` also works.

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
| `narrate` ✦ recommended | Tool calls narrated live, then the final reply | `claude-voice install-interview` |
| `end` | The full final response only | `claude-voice install` |
| `end` + speaker-only | Only the `🔊 Speaker:` line if present | `claude-voice install-speaker` |

---

## Slash commands

Type these directly in the Claude Code prompt:

| Command | What it does |
|---|---|
| `/claude-voice:shh` | Stop speaking immediately |
| `/claude-voice:mode` | Toggle between `end` and `narrate` |
| `/claude-voice:speaker-only` | Speak only the `🔊 Speaker:` summary line |
| `/claude-voice:speaker-full` | Speak the full response (default) |
| `/claude-voice:narrate` | Enable narrate mode (speaks while working) |
| `/claude-voice:narrate-stop` | Disable narrate mode |
| `/claude-voice:config` | Show current configuration |
| `/claude-voice:help` | Show help text |
| `/claude-voice:uninstall` | Remove all hooks and slash commands |

---

## CLI reference

```bash
claude-voice install            # register Stop hook
claude-voice install-speaker    # register Speaker-line extraction
claude-voice install-interview  # register narrate (PreToolUse) hook
claude-voice uninstall          # remove all hooks
claude-voice uninstall-interview

claude-voice speak "hello"      # one-shot TTS test
claude-voice voices             # list available voices
claude-voice config show        # show all settings
claude-voice config set <key> <value>
claude-voice mode               # toggle end ↔ narrate
claude-voice stop               # stop current playback

claude-voice hook stop          # (internal) called by Claude Code Stop hook
claude-voice hook pre-tool      # (internal) called by Claude Code PreToolUse hook
```

---

## Configuration

All settings can be overridden with environment variables or set persistently:

```bash
claude-voice config set voice_en en-GB-SoniaNeural
claude-voice config set speak_mode narrate
claude-voice config set max_chars 800
```

| Key | Env var | Default | Description |
|---|---|---|---|
| `speak_mode` | `CLAUDE_VOICE_SPEAK_MODE` | `end` | `end` · `narrate` |
| `speaker_only` | `CLAUDE_VOICE_SPEAKER_ONLY` | `false` | Speak only the `🔊 Speaker:` line |
| `backend` | `CLAUDE_VOICE_BACKEND` | `edge` | `edge` (online) · `system` (offline) |
| `voice` | `CLAUDE_VOICE_VOICE` | _(unset)_ | Override both EN and ES voices |
| `voice_en` | `CLAUDE_VOICE_VOICE_EN` | `en-US-AriaNeural` | English voice |
| `voice_es` | `CLAUDE_VOICE_VOICE_ES` | `es-MX-DaliaNeural` | Spanish voice |
| `rate` | `CLAUDE_VOICE_RATE` | `0` | Speed offset: Edge uses percent (`-50`..`100`) |
| `max_chars` | `CLAUDE_VOICE_MAX_CHARS` | `1200` | Truncate responses longer than this |
| `wake_word` | `CLAUDE_VOICE_WAKE_WORD` | _(unset)_ | Require this phrase before speaking |
| `focus_pattern` | `CLAUDE_VOICE_FOCUS_PATTERN` | _(unset)_ | Regex — only speak if active window matches |

---

## Voices

List all available Edge voices:

```bash
claude-voice voices
```

Set your preferred voice:

```bash
claude-voice config set voice_en en-GB-RyanNeural    # British male
claude-voice config set voice_es es-ES-ElviraNeural  # Spain Spanish female
```

Language is detected automatically per response (EN/ES). Set `voice` (not `voice_en`/`voice_es`) to force a single voice for all languages.

---

## Status line

Add the current mode to your Claude Code status bar:

```bash
claude-voice install-statusline
```

Shows `🔊 end`, `🔊 narrate`, or `🔇 off` depending on active hooks.

---

## Diagnostics

```bash
claude-voice doctor
```

Checks: Python version, `pygame` playback, Edge TTS connectivity, hooks registered in `~/.claude/settings.json`, slash commands installed.

---

## Uninstall

```bash
# Remove hooks + slash commands (keeps package installed)
claude-voice uninstall

# Remove the package entirely
pipx uninstall claude-voice
```

---

## License

MIT
