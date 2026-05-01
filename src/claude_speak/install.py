"""Patch ~/.claude/settings.json to register / remove the Stop hook and
optionally wire claude-speak into the Claude Code status line."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional


def _resolved_exe() -> str:
    """Find the claude-speak executable. Strategy:

    1. ``sys.argv[0]`` — the script that invoked us, when it's the exe shim.
    2. ``shutil.which`` — checks PATH.
    3. Common Windows pipx locations.
    4. Bare ``claude-speak`` fallback (relies on PATH at hook time).

    Forward slashes are returned so the path works in both git bash and cmd.
    """
    def _ok(p: Optional[str]) -> Optional[str]:
        if not p:
            return None
        # Treat relative or pythonic argv[0] as no-go
        low = p.lower()
        if low.endswith(".py") or low.endswith("__main__.py"):
            return None
        if not Path(p).exists():
            return None
        return p

    # 1. argv[0] when invoked via the .exe shim
    candidate = _ok(sys.argv[0]) if sys.argv else None
    # The shim might appear as `..\Scripts\claude-speak.exe`
    if candidate and "claude-speak" in candidate.lower():
        return str(Path(candidate).resolve()).replace("\\", "/")

    # 2. PATH lookup
    candidate = shutil.which("claude-speak.exe") or shutil.which("claude-speak")
    if _ok(candidate):
        return candidate.replace("\\", "/")  # type: ignore[union-attr]

    # 3. Known pipx + user-bin locations on Windows
    home = Path.home()
    for guess in (
        home / ".local" / "bin" / "claude-speak.exe",
        home / "pipx" / "venvs" / "claude-speak" / "Scripts" / "claude-speak.exe",
        home / ".local" / "bin" / "claude-speak",
    ):
        if guess.exists():
            return str(guess).replace("\\", "/")

    # 4. Last resort
    return "claude-speak"


def _hook_command(args: str) -> str:
    exe = _resolved_exe()
    if " " in exe and not exe.startswith('"'):
        return f'"{exe}" {args}'
    return f"{exe} {args}"


# Resolved at import time so install/uninstall use the correct path.
HOOK_COMMAND = _hook_command("hook stop")
HOOK_EVENT = "Stop"
INTERVIEW_HOOK_COMMAND = _hook_command("hook pre-tool")
INTERVIEW_HOOK_EVENT = "PreToolUse"
POST_TOOL_HOOK_COMMAND = _hook_command("hook post-tool")
POST_TOOL_HOOK_EVENT = "PostToolUse"
STATUSLINE_COMMAND = _hook_command("statusline")


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


def _is_claude_speak_hook(command: str) -> bool:
    return "claude-speak" in (command or "") and "hook stop" in (command or "")


def _is_cv_interview_hook(command: str) -> bool:
    return "claude-speak" in (command or "") and "hook pre-tool" in (command or "")


def _is_cv_post_tool_hook(command: str) -> bool:
    return "claude-speak" in (command or "") and "hook post-tool" in (command or "")


def _strip_hooks_by(entries: list, predicate) -> list:
    cleaned = []
    for entry in entries:
        if not isinstance(entry, dict):
            cleaned.append(entry)
            continue
        kept = [
            h for h in entry.get("hooks", [])
            if not (isinstance(h, dict) and predicate(h.get("command", "")))
        ]
        if kept:
            cleaned.append({**entry, "hooks": kept})
    return cleaned


def _strip_claude_speak_hooks(entries: list) -> list:
    return _strip_hooks_by(entries, _is_claude_speak_hook)


def install_hooks() -> tuple[Path, bool]:
    """(Re)register the Stop and PreToolUse hooks with the *current* absolute path.
    Removes any prior claude-speak entries so we don't end up with duplicates
    after an upgrade that changes how the command is resolved."""
    path = _settings_path()
    settings = _load(path)
    hooks = settings.setdefault("hooks", {})

    stop = hooks.setdefault(HOOK_EVENT, [])
    cleaned_stop = _strip_claude_speak_hooks(stop)
    cleaned_stop.append({"hooks": [{"type": "command", "command": HOOK_COMMAND}]})
    hooks[HOOK_EVENT] = cleaned_stop

    pre_tool = hooks.setdefault(INTERVIEW_HOOK_EVENT, [])
    cleaned_pre = _strip_hooks_by(pre_tool, _is_cv_interview_hook)
    cleaned_pre.append({"hooks": [{"type": "command", "command": INTERVIEW_HOOK_COMMAND}]})
    hooks[INTERVIEW_HOOK_EVENT] = cleaned_pre

    post_tool = hooks.setdefault(POST_TOOL_HOOK_EVENT, [])
    cleaned_post = _strip_hooks_by(post_tool, _is_cv_post_tool_hook)
    cleaned_post.append({"hooks": [{"type": "command", "command": POST_TOOL_HOOK_COMMAND}]})
    hooks[POST_TOOL_HOOK_EVENT] = cleaned_post

    changed = cleaned_stop != stop or cleaned_pre != pre_tool or cleaned_post != post_tool
    if changed:
        _save(path, settings)
    return path, changed


_SPEAKER_BEGIN = "<!-- claude-speak-speaker-begin -->"
_SPEAKER_END = "<!-- claude-speak-speaker-end -->"

_SPEAKER_BLOCK = f"""\
{_SPEAKER_BEGIN}
## Voice mode (claude-speak)

The user is interacting via voice. Their prompts are transcribed audio that
arrives via push-to-talk or always-on dictation. They will read your full
response visually but a TTS engine reads only your **Speaker** line aloud.

End **every** reply with one final line in this exact format:

**🔊 Speaker:** <one-sentence TL;DR, conversational, ≤ 25 words>

Rules for the Speaker line:
- Plain prose only — no code, file paths, commands, or symbol names.
- Speak as if explaining to a person who is *not* looking at a screen.
- Say what was done or what the answer is, not how it works internally.
- If your full reply is already a single short sentence, repeat it.
- Use the same language the user used (Spanish or English).
{_SPEAKER_END}
"""


def install_speaker(*, scope: str = "user") -> tuple[Path, str]:
    """Write the Speaker-line instruction to a CLAUDE.md file.

    ``scope='user'`` writes ~/.claude/CLAUDE.md (applies to every project).
    Returns ``(path, action)`` where action is ``"installed"``,
    ``"updated"``, or ``"kept"``.
    """
    if scope != "user":
        raise ValueError("only scope='user' supported in v1")
    path = Path.home() / ".claude" / "CLAUDE.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    body = path.read_text(encoding="utf-8") if path.exists() else ""

    if _SPEAKER_BEGIN in body and _SPEAKER_END in body:
        # Replace existing block (lets us update wording without dupes)
        pattern = re.compile(
            re.escape(_SPEAKER_BEGIN) + r".*?" + re.escape(_SPEAKER_END),
            re.DOTALL,
        )
        new_body = pattern.sub(_SPEAKER_BLOCK.strip(), body)
        if new_body == body:
            return path, "kept"
        path.write_text(new_body, encoding="utf-8")
        return path, "updated"

    new_body = (body.rstrip() + "\n\n" + _SPEAKER_BLOCK if body.strip() else _SPEAKER_BLOCK)
    path.write_text(new_body, encoding="utf-8")
    return path, "installed"


def uninstall_speaker(*, scope: str = "user") -> tuple[Path, bool]:
    if scope != "user":
        raise ValueError("only scope='user' supported in v1")
    path = Path.home() / ".claude" / "CLAUDE.md"
    if not path.exists():
        return path, False
    body = path.read_text(encoding="utf-8")
    if _SPEAKER_BEGIN not in body:
        return path, False
    pattern = re.compile(
        r"\n*" + re.escape(_SPEAKER_BEGIN) + r".*?" + re.escape(_SPEAKER_END) + r"\n*",
        re.DOTALL,
    )
    new_body = pattern.sub("\n\n", body).strip() + "\n"
    path.write_text(new_body, encoding="utf-8")
    return path, True


def install_statusline(*, force: bool = False) -> tuple[Path, str]:
    """Install ``claude-speak statusline`` as Claude Code's statusLine command.

    Returns ``(path, action)`` where ``action`` is ``"installed"``,
    ``"replaced"``, or ``"kept"`` (already present and not forced).
    """
    path = _settings_path()
    settings = _load(path)
    existing = settings.get("statusLine")
    new_block = {"type": "command", "command": STATUSLINE_COMMAND}

    if existing == new_block:
        return path, "kept"
    if existing and not force:
        return path, "kept"

    settings["statusLine"] = new_block
    _save(path, settings)
    return path, "replaced" if existing else "installed"


def install_interview_hooks() -> tuple[Path, bool]:
    """Install both Stop + PreToolUse hooks for interview mode.

    The Stop hook is added (or kept) first, then the PreToolUse hook.
    Returns (path, changed) where changed=True if PreToolUse hook was new.
    """
    install_hooks()  # ensure Stop hook exists
    path = _settings_path()
    settings = _load(path)
    hooks = settings.setdefault("hooks", {})
    pre_tool = hooks.setdefault(INTERVIEW_HOOK_EVENT, [])

    cleaned = _strip_hooks_by(pre_tool, _is_cv_interview_hook)
    cleaned.append({"hooks": [{"type": "command", "command": INTERVIEW_HOOK_COMMAND}]})

    changed = cleaned != pre_tool
    hooks[INTERVIEW_HOOK_EVENT] = cleaned
    if changed:
        _save(path, settings)
    return path, changed


def uninstall_interview_hooks() -> tuple[Path, bool]:
    """Remove the PreToolUse hook (Stop hook is left in place)."""
    path = _settings_path()
    if not path.exists():
        return path, False
    settings = _load(path)
    hooks = settings.get("hooks", {})
    pre_tool = hooks.get(INTERVIEW_HOOK_EVENT, [])

    cleaned = _strip_hooks_by(pre_tool, _is_cv_interview_hook)
    if cleaned == pre_tool:
        return path, False

    if cleaned:
        hooks[INTERVIEW_HOOK_EVENT] = cleaned
    else:
        hooks.pop(INTERVIEW_HOOK_EVENT, None)
    if not hooks:
        settings.pop("hooks", None)

    _save(path, settings)
    return path, True


def uninstall_hooks() -> tuple[Path, bool]:
    """Remove every claude-speak Stop hook (bare or absolute path form)."""
    path = _settings_path()
    if not path.exists():
        return path, False
    settings = _load(path)
    hooks = settings.get("hooks", {})
    stop = hooks.get(HOOK_EVENT, [])

    cleaned = _strip_claude_speak_hooks(stop)
    if cleaned == stop:
        return path, False

    if cleaned:
        hooks[HOOK_EVENT] = cleaned
    else:
        hooks.pop(HOOK_EVENT, None)
    if not hooks:
        settings.pop("hooks", None)

    _save(path, settings)
    return path, True
