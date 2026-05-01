"""Standalone MP3 player. Spawned as a detached subprocess so audio survives
the parent process exiting (e.g. when the Stop hook returns).

Manages the speaking.lock file so the listener can suppress its own input
while playback is in progress (echo prevention)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

SPEAKING_LOCK = Path.home() / ".claude-voice" / "speaking.lock"


def _set_speaking(active: bool) -> None:
    try:
        if active:
            SPEAKING_LOCK.parent.mkdir(parents=True, exist_ok=True)
            SPEAKING_LOCK.touch()
        else:
            try:
                SPEAKING_LOCK.unlink()
            except FileNotFoundError:
                pass
    except Exception:
        pass


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if len(sys.argv) < 2:
        print("Usage: python -m claude_voice.player <audio-file>", file=sys.stderr)
        return 2
    path = sys.argv[1]

    try:
        import pygame
    except ImportError as exc:
        print(f"pygame missing: {exc}", file=sys.stderr)
        return 1

    try:
        _set_speaking(True)
        pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
    except Exception as exc:
        print(f"playback failed: {exc}", file=sys.stderr)
        return 1
    finally:
        _set_speaking(False)
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        try:
            os.remove(path)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
