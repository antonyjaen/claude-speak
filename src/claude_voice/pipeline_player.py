"""Detached pipeline player: generates edge-tts audio and plays sentences in order.

Spawned by tts.speak_pipeline_detached(). Reads a JSON config file containing
a list of sentences, generates MP3 audio for each via edge-tts (pipelined: next
sentence generates while the current one plays), plays them sequentially, and
keeps speaking.lock alive throughout so the listener suppresses its own input.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

SPEAKING_LOCK = Path.home() / ".claude-voice" / "speaking.lock"


def _touch_lock() -> None:
    try:
        SPEAKING_LOCK.parent.mkdir(parents=True, exist_ok=True)
        SPEAKING_LOCK.touch()
    except Exception:
        pass


def _clear_lock() -> None:
    try:
        SPEAKING_LOCK.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _rate_str(rate: int) -> str:
    return f"+{rate}%" if rate >= 0 else f"{rate}%"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if len(sys.argv) < 2:
        print("Usage: python -m claude_voice.pipeline_player <config.json>", file=sys.stderr)
        return 2

    config_path = sys.argv[1]
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[pipeline_player] config read error: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            os.remove(config_path)
        except OSError:
            pass

    sentences: list[str] = data.get("sentences", [])
    voice: str = data.get("voice", "en-US-AriaNeural")
    rate: int = int(data.get("rate", 0))
    output_device: str = data.get("output_device", "")

    if not sentences:
        return 0

    try:
        import pygame
        import edge_tts
    except ImportError as exc:
        print(f"[pipeline_player] missing dep: {exc}", file=sys.stderr)
        return 1

    # Bounded queue: generate up to 2 sentences ahead of playback
    audio_q: queue.Queue[str | None] = queue.Queue(maxsize=2)

    def _generate() -> None:
        for text in sentences:
            fd, path = tempfile.mkstemp(suffix=".mp3", prefix="cv-")
            os.close(fd)
            try:
                async def _gen(t: str, p: str) -> None:
                    comm = edge_tts.Communicate(t, voice, rate=_rate_str(rate))
                    await comm.save(p)

                asyncio.run(_gen(text, path))
                audio_q.put(path)
            except Exception as exc:
                print(f"[pipeline_player] gen error: {exc}", file=sys.stderr)
                try:
                    os.remove(path)
                except OSError:
                    pass
        audio_q.put(None)  # sentinel

    gen_thread = threading.Thread(target=_generate, daemon=True)
    gen_thread.start()

    _touch_lock()
    try:
        if output_device:
            try:
                pygame.mixer.init(devicename=output_device)
            except Exception as exc:
                print(f"[pipeline_player] device init failed ({exc}); using default", file=sys.stderr)
                pygame.mixer.init()
        else:
            pygame.mixer.init()
        while True:
            try:
                path = audio_q.get(timeout=60)
            except queue.Empty:
                break

            if path is None:
                break

            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    _touch_lock()
                    time.sleep(0.05)
            except Exception as exc:
                print(f"[pipeline_player] play error: {exc}", file=sys.stderr)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
    except Exception as exc:
        print(f"[pipeline_player] fatal: {exc}", file=sys.stderr)
        return 1
    finally:
        _clear_lock()
        try:
            from claude_voice import pidfile as _pf
            _pf.remove("playing", os.getpid())
        except Exception:
            pass
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        # Drain any pre-generated files that won't be played
        try:
            while True:
                leftover = audio_q.get_nowait()
                if leftover is not None:
                    try:
                        os.remove(leftover)
                    except OSError:
                        pass
        except queue.Empty:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
