# claude-voice

Add push-to-talk and text-to-speech to [Claude Code](https://claude.com/claude-code). 100% local + free by default — no API keys required.

- **Speak**: every Claude response is read aloud via the OS-native voice (Windows SAPI / macOS `say` / Linux `espeak-ng`).
- **Listen**: hold a hotkey, talk, release — your speech is transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and typed into the focused terminal.

## Install

```bash
pipx install claude-voice
claude-voice install     # registers the Stop hook in ~/.claude/settings.json
```

> **Linux**: install `espeak-ng` (`sudo apt install espeak-ng`) for TTS.

First run downloads the Whisper model (~150 MB by default) into `~/.cache/huggingface/`.

## Usage

**Speaking** is automatic — every Claude Code response is spoken once installed. Disable temporarily by removing the hook from `~/.claude/settings.json`.

**Listening** runs as a daemon in any terminal:

```bash
claude-voice listen
```

Defaults: hold `F9` to record, release to transcribe + type into the focused window. The daemon doesn't have to be the same terminal as Claude — just have Claude focused when you release the key.

## Commands

| Command | What it does |
|---|---|
| `claude-voice install` | Add Stop hook to `~/.claude/settings.json` |
| `claude-voice uninstall` | Remove the Stop hook |
| `claude-voice listen` | Run the push-to-talk daemon |
| `claude-voice speak <text>` | One-shot TTS, useful for testing |
| `claude-voice transcribe` | One-shot 5s record + transcribe to stdout |
| `claude-voice doctor` | Diagnose audio devices, Whisper model, hooks |
| `claude-voice hook stop` | (internal) called by Claude Code's Stop hook |

## Configuration

Environment variables:

| Var | Default | Description |
|---|---|---|
| `CLAUDE_VOICE_HOTKEY` | `f9` | Push-to-talk key (`pynput` name) |
| `CLAUDE_VOICE_MODEL` | `base.en` | Whisper model — `tiny.en`, `base.en`, `small.en`, `medium.en` |
| `CLAUDE_VOICE_LANG` | `en` | Language code |
| `CLAUDE_VOICE_RATE` | `0` | TTS rate (Windows: -10..10, macOS: WPM, Linux: WPM) |
| `CLAUDE_VOICE_MAX_CHARS` | `1200` | Don't speak more than this per response |
| `CLAUDE_VOICE_AUTO_SUBMIT` | `0` | If `1`, append Enter after typing transcribed text |

## How it works

- **TTS**: Claude Code's `Stop` hook fires after each assistant turn, passing the transcript path. `claude-voice` reads the JSONL, extracts the last assistant message, strips code blocks / markdown, and pipes the result to a native TTS subprocess.
- **STT**: A `pynput` global key listener captures audio with `sounddevice` while the hotkey is held, runs `faster-whisper` locally, and types the transcription into the focused window via `pynput.keyboard.Controller`.

## Limitations / known issues

- Push-to-talk requires the Claude terminal to have focus when you release the hotkey (the daemon types into whatever window is focused).
- Linux Wayland users may need `ydotool` or to run under XWayland — `pynput` keystroke injection has limited Wayland support.
- macOS requires granting Accessibility permission to your terminal app for keystroke injection.
- TTS is non-streaming — the response is spoken after Claude finishes generating.

## Roadmap

- [ ] Streaming TTS (speak as Claude generates)
- [ ] Cloud STT/TTS adapters (OpenAI, ElevenLabs)
- [ ] Wake-word mode (no hotkey)
- [ ] Voice activity detection (auto-stop on silence)
- [ ] System tray UI

## License

MIT
