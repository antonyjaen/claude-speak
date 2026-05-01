"""File-backed runtime config at ``~/.claude-speak/config.json``.

Precedence for any key: config file > environment variable > built-in default.
Reads happen on every ``get()`` so daemons pick up changes without a restart.
Writes are atomic (temp file + rename).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

CONFIG_PATH = Path.home() / ".claude-speak" / "config.json"

# Map config keys -> (env var name, default value, type-coercer or None)
SCHEMA: dict[str, tuple[str, Any, Optional[type]]] = {
    "focus_pattern":  ("CLAUDE_SPEAK_FOCUS_PATTERN",  "", str),
    "hotkey":         ("CLAUDE_SPEAK_HOTKEY",         "f9", str),
    "auto_submit":    ("CLAUDE_SPEAK_AUTO_SUBMIT",    False, bool),
    "rms_threshold":  ("CLAUDE_SPEAK_RMS_THRESHOLD",  0.012, float),
    "model":          ("CLAUDE_SPEAK_MODEL",          "base", str),
    "lang":           ("CLAUDE_SPEAK_LANG",           "en", str),
    "backend":        ("CLAUDE_SPEAK_BACKEND",        "edge", str),
    "voice":          ("CLAUDE_SPEAK_VOICE",          "", str),
    "voice_en":       ("CLAUDE_SPEAK_VOICE_EN",       "en-US-AriaNeural", str),
    "voice_es":       ("CLAUDE_SPEAK_VOICE_ES",       "es-MX-DaliaNeural", str),
    "rate":           ("CLAUDE_SPEAK_RATE",           0, int),
    "max_chars":      ("CLAUDE_SPEAK_MAX_CHARS",      1200, int),
    "wake_word":      ("CLAUDE_SPEAK_WAKE_WORD",      "claude", str),
    "speaker_only":   ("CLAUDE_SPEAK_SPEAKER_ONLY",   False, bool),
    "speak_mode":     ("CLAUDE_SPEAK_SPEAK_MODE",     "end", str),
}

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "", "false", "no", "off"}


def _coerce(value: Any, target: Optional[type]) -> Any:
    if target is None or value is None:
        return value
    if target is bool:
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
        return False
    try:
        return target(value)
    except (TypeError, ValueError):
        return value


def load() -> dict:
    """Return the current config dict (raw file contents). Empty if missing/invalid."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save(data: dict) -> None:
    """Atomic write."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix="config-", suffix=".json", dir=str(CONFIG_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get(key: str, default: Any = None) -> Any:
    """Return the effective value for ``key``.

    Resolution: if the key is *present* in the config file (including with an
    explicit empty string), the file value wins. If absent, fall back to env
    var, then schema default, then ``default``.
    """
    if key not in SCHEMA:
        return load().get(key, default)
    env_name, schema_default, target = SCHEMA[key]

    data = load()
    if key in data:
        return _coerce(data[key], target)

    env_val = os.environ.get(env_name)
    if env_val is not None and env_val != "":
        return _coerce(env_val, target)

    return schema_default if schema_default is not None else default


def set_value(key: str, value: Any) -> dict:
    """Set a key. ``None`` removes it (falls back to env/default). Empty string
    is stored explicitly so it overrides any env var."""
    data = load()
    if value is None:
        data.pop(key, None)
    else:
        if key in SCHEMA:
            value = _coerce(value, SCHEMA[key][2])
        data[key] = value
    save(data)
    return data


def reset(key: Optional[str] = None) -> dict:
    """Remove a key (or every key if ``key`` is None)."""
    if key is None:
        save({})
        return {}
    data = load()
    data.pop(key, None)
    save(data)
    return data


def effective() -> dict:
    """Return all schema keys with their currently effective values + sources."""
    data = load()
    out = {}
    for key, (env_name, default, target) in SCHEMA.items():
        if key in data:
            out[key] = {"value": _coerce(data[key], target), "source": "config"}
        else:
            env_val = os.environ.get(env_name)
            if env_val is not None and env_val != "":
                out[key] = {"value": _coerce(env_val, target), "source": f"env ({env_name})"}
            else:
                out[key] = {"value": default, "source": "default"}
    return out
