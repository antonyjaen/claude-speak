"""Cross-platform text-to-speech using OS-native engines.

Windows: PowerShell + System.Speech (no install required).
macOS:   `say` (built in).
Linux:   `espeak-ng` (preferred), then `espeak`, then `spd-say`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from typing import Optional


_PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = {rate}
$text = [Console]::In.ReadToEnd()
$s.Speak($text)
"""


_current_lock = threading.Lock()
_current_proc: Optional[subprocess.Popen] = None


def _rate_env() -> int:
    try:
        return int(os.environ.get("CLAUDE_VOICE_RATE", "0"))
    except ValueError:
        return 0


def _spawn_windows(text: str) -> subprocess.Popen:
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


def _spawn_macos(text: str) -> subprocess.Popen:
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
        # spd-say doesn't read stdin; pass text as arg
        return subprocess.Popen(
            ["spd-say", "--wait", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    raise RuntimeError(
        "No TTS engine found. Install espeak-ng: sudo apt install espeak-ng"
    )


def speak(text: str, *, blocking: bool = True) -> Optional[subprocess.Popen]:
    """Speak `text` using the platform-native TTS engine.

    Stops any speech already in progress. Returns the subprocess object so the
    caller can interrupt with `stop_speaking()`.
    """
    text = (text or "").strip()
    if not text:
        return None

    stop_speaking()

    if sys.platform == "win32":
        proc = _spawn_windows(text)
    elif sys.platform == "darwin":
        proc = _spawn_macos(text)
    else:
        proc = _spawn_linux(text)

    if proc.stdin is not None:
        try:
            proc.stdin.write(text)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    with _current_lock:
        global _current_proc
        _current_proc = proc

    if blocking:
        try:
            proc.wait()
        except KeyboardInterrupt:
            stop_speaking()
            raise
        return None

    return proc


def stop_speaking() -> None:
    """Interrupt any TTS currently playing."""
    global _current_proc
    with _current_lock:
        proc = _current_proc
        _current_proc = None
    if proc is None:
        return
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass
