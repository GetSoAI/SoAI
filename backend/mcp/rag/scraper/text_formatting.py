"""SoAI - Web scraper text formatting utilities [backend/mcp/rag/scraper/text_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

__all__ = (
    "normalize_markdown_to_text",
    "resolve_extract_mode_content",
    "truncate_text",
)


def normalize_markdown_to_text(markdown: str) -> str:
    if not markdown:
        return ""
    text = markdown
    text = re.sub(r"^```[a-zA-Z0-9_-]*\s*$", "", text, flags=re.MULTILINE)
    text = text.replace("```", "")
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}\d+\.\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def resolve_extract_mode_content(
    *,
    content: str,
    content_type: str,
    source_html: str | None,
    extract_mode: str,
) -> tuple[str, str]:
    if extract_mode == "text" and content_type == "markdown":
        return normalize_markdown_to_text(content), "text"
    if extract_mode == "html" and isinstance(source_html, str):
        return source_html, "html"
    return content, content_type


def truncate_text(value: str, *, max_chars: int) -> tuple[str, bool]:
    if not value:
        return ("", False)
    if len(value) <= max_chars:
        return (value, False)
    suffix = "\n…"
    if max_chars <= len(suffix):
        return (value[:max_chars], True)
    head = value[: max_chars - len(suffix)].rstrip()
    return (f"{head}{suffix}", True)
