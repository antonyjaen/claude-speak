"""Entry points called by Claude Code hooks."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from claude_voice import filters, transcript, tts


def _max_chars() -> int:
    try:
        return int(os.environ.get("CLAUDE_VOICE_MAX_CHARS", "1200"))
    except ValueError:
        return 1200


def stop_hook() -> int:
    """Read the Stop-hook payload from stdin and speak the last assistant message.

    Hook payload (per Claude Code docs):
        {
          "session_id": "...",
          "transcript_path": "/abs/path/to/session.jsonl",
          "stop_hook_active": false,
          "hook_event_name": "Stop"
        }
    """
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if payload.get("stop_hook_active"):
        # Avoid recursive triggers
        return 0

    path = payload.get("transcript_path")
    if not path:
        return 0

    text = transcript.last_assistant_text(Path(path))
    if not text.strip():
        return 0

    cleaned = filters.clean_for_speech(text, max_chars=_max_chars())
    if not cleaned:
        return 0

    try:
        tts.speak(cleaned, blocking=False)
    except Exception as exc:
        # Hooks must not break Claude Code on failure.
        print(f"claude-voice: tts failed: {exc}", file=sys.stderr)
        return 0

    return 0
