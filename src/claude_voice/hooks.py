"""Entry points called by Claude Code hooks."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from claude_voice import filters, transcript, tts

_STATE_DIR = Path.home() / ".claude-voice" / "sessions"
_PRIMARY_SESSION_FILE = Path.home() / ".claude-voice" / "primary_session"

_SPEAKER_STRIP = re.compile(
    r"\n*(?:\*\*\s*)?🔊?\s*(?:Speaker|Hablante)\s*:.*$",
    re.IGNORECASE | re.MULTILINE,
)


def _spoken_path(session_id: str) -> Path:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    return _STATE_DIR / f"{safe}.spoken"


def _read_spoken(session_id: str) -> int:
    try:
        return int(_spoken_path(session_id).read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_spoken(session_id: str, n: int) -> None:
    _spoken_path(session_id).write_text(str(n), encoding="utf-8")


def _clear_spoken(session_id: str) -> None:
    try:
        _spoken_path(session_id).unlink()
    except FileNotFoundError:
        pass


def _is_subagent(payload: dict) -> bool:
    """Return True if this hook is firing inside a subagent (Agent tool spawn)."""
    return bool(payload.get("parent_session_id"))


def _acquire_primary(session_id: str) -> bool:
    """Claim TTS for this session. Returns False if a different session is actively speaking."""
    try:
        _PRIMARY_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _PRIMARY_SESSION_FILE.exists():
            owner = _PRIMARY_SESSION_FILE.read_text(encoding="utf-8").strip()
            if owner and owner != session_id and tts.is_speaking():
                return False
        _PRIMARY_SESSION_FILE.write_text(session_id, encoding="utf-8")
        return True
    except Exception:
        return True


def _max_chars() -> int:
    from claude_voice import config
    try:
        return int(config.get("max_chars", 1200))
    except (TypeError, ValueError):
        return 1200


def _speak_mode() -> str:
    from claude_voice import config
    return str(config.get("speak_mode", "end")).lower().strip()


def _emit(sentences: list[str], *, queue: bool = False) -> None:
    if not sentences:
        return
    try:
        if queue:
            tts.speak_queued(sentences)
        else:
            tts.speak_pipeline_detached(sentences)
    except Exception as exc:
        print(f"claude-voice: tts failed: {exc}", file=sys.stderr)


def _clean_mid(text: str) -> list[str]:
    """Clean text for a mid-response narration (no Speaker line)."""
    cleaned = _SPEAKER_STRIP.sub("", text).strip()
    cleaned = filters.clean_for_speech(cleaned, max_chars=_max_chars())
    return filters.split_sentences(cleaned)


def _speak_ask_question(payload: dict) -> None:
    tool_input = payload.get("tool_input") or {}
    questions = tool_input.get("questions") or []
    if not questions:
        return

    parts: list[str] = []

    for qi, q in enumerate(questions):
        prefix = f"Question {qi + 1}: " if len(questions) > 1 else ""
        multi = " Select all that apply." if q.get("multiSelect") else ""
        parts.append(f"{prefix}{q['question']}{multi}")
        for oi, opt in enumerate(q.get("options") or []):
            label = opt.get("label", "")
            desc = opt.get("description", "")
            parts.append(f"{oi + 1}. {label}. {desc}" if desc else f"{oi + 1}. {label}.")

    _emit(parts)


def pre_tool_hook() -> int:
    """PreToolUse hook: speak AskUserQuestion options (always) and Claude's
    narration text before each tool call (interview mode only).
    """
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if _is_subagent(payload):
        return 0

    if payload.get("tool_name") == "AskUserQuestion":
        session_id = payload.get("session_id", "unknown")
        _acquire_primary(session_id)
        _speak_ask_question(payload)
        return 0

    if _speak_mode() not in ("narrate", "interview"):
        return 0

    session_id = payload.get("session_id", "unknown")
    if not _acquire_primary(session_id):
        return 0

    path = payload.get("transcript_path")
    if not path:
        return 0

    all_texts = transcript.all_assistant_texts(Path(path))
    if not all_texts:
        return 0

    spoken = _read_spoken(session_id)
    new_texts = all_texts[spoken:]
    if not new_texts:
        return 0

    _write_spoken(session_id, len(all_texts))

    sentences: list[str] = []
    for text in new_texts:
        sentences.extend(_clean_mid(text))
    _emit(sentences, queue=True)
    return 0


def post_tool_hook() -> int:
    """PostToolUse hook: stop TTS as soon as AskUserQuestion is answered."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if payload.get("tool_name") == "AskUserQuestion":
        try:
            tts.stop()
        except Exception:
            pass
    return 0


def stop_hook() -> int:
    """Stop hook: speak the final assistant message after Claude finishes.

    In 'end' mode (default): speaks only the last message (Speaker line preferred).
    In 'interview' mode: speaks any unspoken final text, then the Speaker line.
    """
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if payload.get("stop_hook_active"):
        return 0

    if _is_subagent(payload):
        return 0

    session_id = payload.get("session_id", "unknown")
    if not _acquire_primary(session_id):
        return 0

    path = payload.get("transcript_path")
    if not path:
        return 0

    from claude_voice import config as _config
    mode = _speak_mode()
    speaker_only = bool(_config.get("speaker_only", False))

    if mode in ("narrate", "interview"):
        all_texts = transcript.all_assistant_texts(Path(path))
        spoken = _read_spoken(session_id)
        new_texts = all_texts[spoken:]

        if not new_texts:
            return 0

        sentences: list[str] = []
        for i, text in enumerate(new_texts):
            is_last = i == len(new_texts) - 1
            if is_last:
                speaker = filters.extract_speaker_section(text)
                if speaker is not None:
                    sentences.append(speaker)
                elif not speaker_only:
                    sentences.extend(_clean_mid(text))
            else:
                sentences.extend(_clean_mid(text))

        _write_spoken(session_id, len(all_texts))
        _emit(sentences, queue=True)
        return 0

    # Default "end" mode
    text = transcript.last_assistant_text(Path(path))
    if not text.strip():
        return 0

    speaker = filters.extract_speaker_section(text)
    if speaker is None:
        if speaker_only:
            return 0
        full = filters.clean_for_speech(text, max_chars=_max_chars())
        sentences = filters.split_sentences(full)
    else:
        sentences = [speaker]

    _emit(sentences)
    return 0
