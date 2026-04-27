"""Clean Claude's text output for TTS — strip code, markdown, ANSI, cap length."""
from __future__ import annotations

import re

_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_BOLD_ITALIC = re.compile(r"\*{1,3}([^*]+)\*{1,3}")
_MD_HEADING = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MD_HR = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_MD_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)
_HTML_TAG = re.compile(r"<[^>]+>")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+$", re.MULTILINE)


def clean_for_speech(text: str, max_chars: int = 1200) -> str:
    """Return a TTS-friendly version of `text`.

    Replaces fenced code blocks with a short placeholder, strips markdown
    formatting, removes ANSI escapes, and truncates at a sentence boundary.
    """
    if not text:
        return ""

    def _code_placeholder(match: re.Match[str]) -> str:
        body = match.group(0)
        lines = body.count("\n")
        return f" (code block, {lines} lines) " if lines > 1 else " (code block) "

    out = _CODE_FENCE.sub(_code_placeholder, text)
    out = _ANSI.sub("", out)
    out = _HTML_TAG.sub("", out)
    out = _MD_LINK.sub(r"\1", out)
    out = _INLINE_CODE.sub(r"\1", out)
    out = _MD_BOLD_ITALIC.sub(r"\1", out)
    out = _MD_HEADING.sub("", out)
    out = _MD_HR.sub("", out)
    out = _MD_BLOCKQUOTE.sub("", out)
    out = _TRAILING_WS.sub("", out)
    out = _MULTI_NEWLINE.sub("\n\n", out).strip()

    if len(out) > max_chars:
        truncated = out[:max_chars]
        # Back up to a sentence boundary if we can find one in the last 200 chars
        for sep in (". ", "! ", "? ", "\n"):
            idx = truncated.rfind(sep, max_chars - 200)
            if idx != -1:
                truncated = truncated[: idx + len(sep)]
                break
        out = truncated.rstrip() + " (response truncated)"

    return out
