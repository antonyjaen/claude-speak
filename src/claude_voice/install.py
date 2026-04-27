"""Patch ~/.claude/settings.json to register / remove the Stop hook."""
from __future__ import annotations

import json
from pathlib import Path

HOOK_COMMAND = "claude-voice hook stop"
HOOK_EVENT = "Stop"


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{path} is not valid JSON ({exc}); refusing to overwrite. "
            "Fix it manually and re-run."
        ) from exc


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _has_command(entries: list, command: str) -> bool:
    for entry in entries:
        for hook in entry.get("hooks", []) if isinstance(entry, dict) else []:
            if isinstance(hook, dict) and hook.get("command") == command:
                return True
    return False


def install_hooks() -> tuple[Path, bool]:
    """Add the Stop hook. Returns (path, added) where added is False if no-op."""
    path = _settings_path()
    settings = _load(path)
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault(HOOK_EVENT, [])

    if _has_command(stop, HOOK_COMMAND):
        return path, False

    stop.append({"hooks": [{"type": "command", "command": HOOK_COMMAND}]})
    _save(path, settings)
    return path, True


def uninstall_hooks() -> tuple[Path, bool]:
    """Remove the Stop hook. Returns (path, removed)."""
    path = _settings_path()
    if not path.exists():
        return path, False
    settings = _load(path)
    hooks = settings.get("hooks", {})
    stop = hooks.get(HOOK_EVENT, [])

    new_stop = []
    removed = False
    for entry in stop:
        if not isinstance(entry, dict):
            new_stop.append(entry)
            continue
        kept_hooks = [
            h for h in entry.get("hooks", [])
            if not (isinstance(h, dict) and h.get("command") == HOOK_COMMAND)
        ]
        if len(kept_hooks) != len(entry.get("hooks", [])):
            removed = True
        if kept_hooks:
            new_stop.append({**entry, "hooks": kept_hooks})

    if not removed:
        return path, False

    if new_stop:
        hooks[HOOK_EVENT] = new_stop
    else:
        hooks.pop(HOOK_EVENT, None)
    if not hooks:
        settings.pop("hooks", None)

    _save(path, settings)
    return path, True
