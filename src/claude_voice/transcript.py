"""Read Claude Code session transcripts (JSONL) and extract assistant text."""
from __future__ import annotations

import json
from pathlib import Path


def last_assistant_text(transcript_path: Path) -> str:
    """Return the text of the most recent assistant message in the transcript.

    Returns an empty string if the file is missing or has no assistant text.
    """
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

    message = last_assistant.get("message") or {}
    content = message.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                txt = block.get("text", "")
                if txt:
                    parts.append(txt)
        return "\n\n".join(parts)

    return ""
