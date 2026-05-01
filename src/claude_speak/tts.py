"""Cross-platform text-to-speech with selectable backends.

While speech is playing, a ``speaking.lock`` file is touched at
``~/.claude-speak/speaking.lock`` so the listener can skip audio while we're
talking (echo / feedback suppression for conversation mode).

Backends (env var ``claude_speak_BACKEND``):
  * ``edge``   (default) — Microsoft Edge neural voices via the free public
    edge-tts API. Online, high quality, dozens of voices.
  * ``system`` — OS-native engines. Offline, lower quality.
    - Windows: PowerShell + System.Speech (SAPI)
    - macOS: ``say``
    - Linux: ``espeak-ng`` then ``espeak`` then ``spd-say``

Voice (env var ``claude_speak_VOICE``): for the ``edge`` backend, an Azure
voice name like ``en-US-AriaNeural``. List options with ``claude-speak voices``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

# Suppress pygame's startup banner before any pygame import path is touched.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

SPEAKING_LOCK = Path.home() / ".claude-speak" / "speaking.lock"


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


def is_speaking() -> bool:
    return SPEAKING_LOCK.exists()


_PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = {rate}
$text = [Console]::In.ReadToEnd()
$s.Speak($text)
"""


_state_lock = threading.Lock()
_current: Optional[tuple[str, object]] = None  # ("proc"|"pygame", handle)
_pygame_inited = False


from claude_speak import config as _config


def _backend() -> str:
    return str(_config.get("backend", "edge")).strip().lower()


_DEFAULT_VOICE_EN = "en-US-AriaNeural"
_DEFAULT_VOICE_ES = "es-MX-DaliaNeural"

def _voice(_text: Optional[str] = None) -> str:
    """Return the voice to use based on config lang setting.

    Resolution order:
      1. ``voice`` — explicit override, language-agnostic
      2. ``voice_es`` / ``voice_en`` based on ``lang`` config key
    """
    explicit = _config.get("voice", "")
    if explicit:
        return str(explicit)
    lang = str(_config.get("lang", "en")).strip().lower()
    if lang == "es":
        return str(_config.get("voice_es", _DEFAULT_VOICE_ES))
    return str(_config.get("voice_en", _DEFAULT_VOICE_EN))


def _rate_env() -> int:
    try:
        return int(_config.get("rate", 0))
    except (TypeError, ValueError):
        return 0


# ---------- system backend ----------
def _spawn_windows() -> subprocess.Popen:
    rate = _rate_env()
    script = _PS_SCRIPT.format(rate=rate)
    return subprocess.Popen(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )


def _spawn_macos() -> subprocess.Popen:
    rate = _rate_env()
    args = ["say"]
    if rate:
        args += ["-r", str(rate)]
    return subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )


def _spawn_linux(text: str) -> subprocess.Popen:
    for binary in ("espeak-ng", "espeak"):
        if shutil.which(binary):
            args = [binary]
            rate = _rate_env()
            if rate:
                args += ["-s", str(rate)]
            return subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
            )
    if shutil.which("spd-say"):
        return subprocess.Popen(
            ["spd-say", "--wait", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    raise RuntimeError(
        "No TTS engine found. Install espeak-ng: sudo apt install espeak-ng"
    )


def _speak_system(text: str, blocking: bool) -> None:
    if sys.platform == "win32":
        proc = _spawn_windows()
    elif sys.platform == "darwin":
        proc = _spawn_macos()
    else:
        proc = _spawn_linux(text)

    if proc.stdin is not None:
        try:
            proc.stdin.write(text)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    with _state_lock:
        global _current
        _current = ("proc", proc)

    if blocking:
        try:
            proc.wait()
        except KeyboardInterrupt:
            stop_speaking()
            raise


# ---------- edge backend ----------
def _format_rate(rate: int) -> str:
    """edge-tts rate format is ``+N%`` or ``-N%`` relative to default."""
    return f"+{rate}%" if rate >= 0 else f"{rate}%"


def _edge_to_mp3(text: str, voice: str, rate: int) -> str:
    import asyncio

    import edge_tts

    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="claude-speak-")
    os.close(fd)

    async def _gen() -> None:
        comm = edge_tts.Communicate(text, voice, rate=_format_rate(rate))
        await comm.save(path)

    try:
        asyncio.run(_gen())
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    return path


def _ensure_pygame() -> None:
    global _pygame_inited
    if _pygame_inited:
        return
    import pygame

    pygame.mixer.init()
    _pygame_inited = True


def _play_blocking(path: str) -> None:
    _ensure_pygame()
    import pygame

    _set_speaking(True)
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    with _state_lock:
        global _current
        _current = ("pygame", path)
    try:
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
    except KeyboardInterrupt:
        stop_speaking()
        raise
    finally:
        _set_speaking(False)
        try:
            os.remove(path)
        except OSError:
            pass


def _windowless_python() -> str:
    """Use ``pythonw.exe`` on Windows so the player doesn't flash a console."""
    if sys.platform != "win32":
        return sys.executable
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return pythonw if Path(pythonw).exists() else sys.executable


def _play_detached(path: str) -> None:
    """Spawn a subprocess that survives this process exiting."""
    kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = (
            DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        [_windowless_python(), "-m", "claude_speak.player", path],
        **kwargs,
    )
    with _state_lock:
        global _current
        _current = ("proc", proc)
    # Register PID so `claude-speak stop` can find it.
    try:
        from claude_speak import pidfile
        pidfile.append("playing", proc.pid)
    except Exception:
        pass


def _speak_edge(text: str, blocking: bool) -> None:
    voice = _voice(text)
    rate = _rate_env()
    path = _edge_to_mp3(text, voice, rate)
    if blocking:
        _play_blocking(path)
    else:
        _play_detached(path)


# ---------- public api ----------
def speak(text: str, *, blocking: bool = True) -> None:
    """Speak ``text``. Falls back from ``edge`` to ``system`` on failure."""
    text = (text or "").strip()
    if not text:
        return None

    stop_speaking()

    backend = _backend()
    if backend == "edge":
        try:
            _speak_edge(text, blocking=blocking)
            return None
        except Exception as exc:
            print(
                f"[claude-speak] edge-tts failed "
                f"({exc.__class__.__name__}: {exc}); falling back to system TTS",
                file=sys.stderr,
            )

    _speak_system(text, blocking=blocking)
    return None


def stop_speaking() -> None:
    """Interrupt any TTS currently playing."""
    global _current
    with _state_lock:
        cur = _current
        _current = None
    # Always clear the lock — handles abrupt process kills on Windows where
    # finally blocks don't run after TerminateProcess().
    _set_speaking(False)
    if cur is None:
        return
    kind, handle = cur
    if kind == "proc":
        try:
            proc = handle  # type: ignore[assignment]
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass
    elif kind == "pygame":
        try:
            import pygame

            pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            os.remove(str(handle))
        except OSError:
            pass


def _launch_pipeline(sentences: list[str]) -> None:
    """Spawn pipeline_player for sentences without stopping current speech."""
    import json
    import tempfile

    voice = _voice(sentences[0])
    rate = _rate_env()

    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="cv-sents-")
    os.close(fd)
    payload: dict = {"sentences": sentences, "voice": voice, "rate": rate}
    Path(tmp).write_text(json.dumps(payload), encoding="utf-8")

    kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = (
            DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        [_windowless_python(), "-m", "claude_speak.pipeline_player", tmp],
        **kwargs,
    )
    with _state_lock:
        global _current
        _current = ("proc", proc)
    try:
        from claude_speak import pidfile
        pidfile.append("playing", proc.pid)
    except Exception:
        pass


def speak_pipeline_detached(sentences: list[str]) -> None:
    """Interrupt any current speech, then play sentences via detached pipeline_player."""
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return
    stop_speaking()
    _launch_pipeline(sentences)


def wait_for_silence(timeout: float = 15.0) -> None:
    """Block until speaking.lock is gone (or timeout expires)."""
    deadline = time.monotonic() + timeout
    while is_speaking():
        if time.monotonic() >= deadline:
            break
        time.sleep(0.05)


def speak_queued(sentences: list[str]) -> None:
    """Wait for current speech to finish, then play sentences without interrupting."""
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return
    wait_for_silence()
    _launch_pipeline(sentences)


# ---------- introspection ----------
def list_edge_voices(language: Optional[str] = None) -> list[dict]:
    """Return all edge-tts voices, optionally filtered by language prefix
    (e.g. ``en``, ``en-US``)."""
    import asyncio

    import edge_tts

    async def _list() -> list[dict]:
        return await edge_tts.list_voices()

    voices = asyncio.run(_list())
    if language:
        prefix = language.lower()
        voices = [
            v for v in voices if v.get("Locale", "").lower().startswith(prefix)
        ]
    return voices
