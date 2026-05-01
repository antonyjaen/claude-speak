"""Clean Claude's text output for TTS — strip code, markdown, ANSI, cap length.

If the text contains a ``**🔊 Speaker:** ...`` line (or one of its variants),
:func:`extract_speaker_section` returns just that line so the Stop hook can
read a TL;DR instead of the whole reply.
"""
from __future__ import annotations

import re
from typing import Optional

_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_SENT_BOUNDARY = re.compile(r'(?<=[.!?…])\s+(?=\S)')
_PARA_BREAK = re.compile(r'\n\n+')
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


# Match a "Speaker" line that Claude is told (via CLAUDE.md instructions) to
# end its replies with. Tolerant of formatting variations.
#   **🔊 Speaker:** ...
#   **Speaker:** ...
#   🔊 Speaker: ...
_SPEAKER_LINE = re.compile(
    r"(?:\*\*\s*)?🔊?\s*(?:Speaker|Hablante)\s*:\s*(?:\*\*\s*)?(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_speaker_section(text: str) -> Optional[str]:
    """Return the contents of the last Speaker line in ``text``, or ``None``.

    Designed to capture a single-sentence TL;DR Claude appends specifically
    for TTS. Multiple speaker lines: the last one wins (closest to the end).
    """
    if not text:
        return None
    matches = list(_SPEAKER_LINE.finditer(text))
    if not matches:
        return None
    raw = matches[-1].group(1)
    # Drop trailing markdown bold markers and whitespace
    return raw.replace("**", "").strip() or None


def clean_for_speech(text: str, max_chars: int = 1200) -> str:
    """Return a TTS-friendly version of `text`.

    Strips fenced code blocks entirely (no announcement), removes markdown
    formatting, removes ANSI escapes, and truncates at a sentence boundary.
    """
    if not text:
        return ""

    out = _CODE_FENCE.sub(" ", text)  # silently drop code; don't announce it
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


def split_sentences(text: str, min_chars: int = 30) -> list[str]:
    """Split TTS-cleaned text into speakable sentence chunks.

    Splits on sentence-ending punctuation and paragraph breaks, merging very
    short fragments into their neighbor so each chunk feels like a complete
    thought when spoken aloud.
    """
    if not text:
        return []
    parts: list[str] = []
    for para in _PARA_BREAK.split(text):
        para = para.strip()
        if not para:
            continue
        raw = _SENT_BOUNDARY.split(para)
        buf = ""
        for s in raw:
            s = s.strip()
            if not s:
                continue
            if buf:
                if len(buf) < min_chars:
                    buf = buf + " " + s
                else:
                    parts.append(buf)
                    buf = s
            else:
                buf = s
        if buf:
            parts.append(buf)
    return [p for p in parts if p.strip()]
