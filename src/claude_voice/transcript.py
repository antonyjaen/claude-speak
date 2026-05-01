"""Read Claude Code session transcripts (JSONL) and extract assistant text."""
from __future__ import annotations

import json
from pathlib import Path


def _extract_text_blocks(content) -> str:
    """Return only text-type blocks from message content (skips tool_use etc.)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                txt = block.get("text", "")
                if txt:
                    parts.append(txt)
        return "\n\n".join(parts)
    return ""


def last_assistant_text(transcript_path: Path) -> str:
    """Return the text of the most recent assistant message in the transcript."""
    path = Path(transcript_path)
    if not path.exists():
        return ""

    last_assistant: dict | None = None
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "assistant":
                last_assistant = obj

    if not last_assistant:
        return ""

    content = (last_assistant.get("message") or {}).get("content")
    return _extract_text_blocks(content)


def all_assistant_texts(transcript_path: Path) -> list[str]:
    """Return text-only content from every assistant turn in the transcript.

    Each element is the combined text blocks of one assistant message.
    Tool-use and other non-text blocks are excluded so only narration is returned.
    """
    path = Path(transcript_path)
    if not path.exists():
        return []

    texts: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "assistant":
                continue
            content = (obj.get("message") or {}).get("content")
            combined = _extract_text_blocks(content)
            if combined.strip():
                texts.append(combined)

    return texts
