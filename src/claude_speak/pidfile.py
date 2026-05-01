"""Tiny pidfile-based IPC for tracking running claude-speak processes.

Used so `claude-speak stop` can interrupt TTS started by the Stop hook and
`claude-speak listen --stop` can shut down a backgrounded listener.
"""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".claude-speak"


def _path(name: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{name}.pid"


def write(name: str, pid: int | None = None) -> Path:
    """Record a PID for the named slot. Defaults to current process."""
    pid = pid if pid is not None else os.getpid()
    p = _path(name)
    p.write_text(str(pid), encoding="utf-8")
    return p


def append(name: str, pid: int) -> Path:
    """Add a PID to a slot that may hold many (e.g. concurrent TTS players)."""
    p = _path(name)
    existing = read_all(name)
    if pid not in existing:
        existing.append(pid)
    p.write_text("\n".join(str(x) for x in existing) + "\n", encoding="utf-8")
    return p


def read(name: str) -> int | None:
    p = _path(name)
    if not p.exists():
        return None
    try:
        return int(p.read_text(encoding="utf-8").splitlines()[0].strip())
    except (ValueError, IndexError):
        return None


def read_all(name: str) -> list[int]:
    p = _path(name)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(int(line))
        except ValueError:
            continue
    return out


def remove(name: str, pid: int) -> None:
    """Remove one PID from a multi-pid slot."""
    p = _path(name)
    existing = [x for x in read_all(name) if x != pid]
    if existing:
        p.write_text("\n".join(str(x) for x in existing) + "\n", encoding="utf-8")
    else:
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def clear(name: str) -> None:
    p = _path(name)
    try:
        p.unlink()
    except FileNotFoundError:
        pass


def is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not h:
            return False
        try:
            exit_code = ctypes.c_ulong(0)
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
            if not ok:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def kill(pid: int) -> bool:
    if pid <= 0 or not is_alive(pid):
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_TERMINATE = 0x0001
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if not h:
            return False
        try:
            return bool(ctypes.windll.kernel32.TerminateProcess(h, 1))
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False
