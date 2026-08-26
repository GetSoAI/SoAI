"""SoAI - Internal inline Markdown rendering helpers [backend/mcp/rag/scraper/markdown_inline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Callable

from bs4 import (
    BeautifulSoup,
    Comment,
    Declaration,
    Doctype,
    ProcessingInstruction,
    Tag,
)
from bs4.element import NavigableString, PageElement

__all__ = (
    "code_fence",
    "escape_table_cell",
    "indent_block",
    "normalize_document_markdown",
    "normalize_inline_whitespace",
    "render_inline_children",
    "render_inline_fragment",
)

IGNORED_HTML_TAGS: frozenset[str] = frozenset({"script", "style", "noscript"})

_MARKDOWN_ESCAPE_PATTERN = r"([\\`*_{}\[\]#+!|])"
_WHITESPACE_PATTERN = r"[ \t\r\f\v]+"
_PUNCTUATION_SPACING_PATTERN = r" +([,.;:?])"


def normalize_inline_whitespace(text: str) -> str:
    collapsed = re.sub(_WHITESPACE_PATTERN, " ", text)
    no_padding = re.sub(" *\n *", "\n", collapsed)
    tightened = re.sub(_PUNCTUATION_SPACING_PATTERN, r"\1", no_padding)
    return re.sub("\n{3,}", "\n\n", tightened).strip()


def normalize_document_markdown(text: str) -> str:
    collapsed = re.sub("\n{3,}", "\n\n", text).strip()
    return f"{collapsed}\n" if collapsed else ""


def escape_table_cell(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def code_fence(text: str) -> str:
    max_run = 0
    for match in re.finditer("`+", text):
        max_run = max(max_run, len(match.group(0)))
    return "`" * max(3, max_run + 1)


def indent_block(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    return "\n".join(f"  {line}" if line else "" for line in lines)


def render_inline_children(
    node: Tag | BeautifulSoup,
    *,
    code_language_resolver: Callable[[Tag], str],
) -> str:
    text = "".join(
        render_inline_fragment(child, code_language_resolver=code_language_resolver)
        for child in node.children
    )
    return normalize_inline_whitespace(text)


def render_inline_fragment(
    node: PageElement | None,
    *,
    code_language_resolver: Callable[[Tag], str],
) -> str:
    return _render_inline_node(node, code_language_resolver=code_language_resolver)


def _escape_markdown_text(text: str) -> str:
    return re.sub(_MARKDOWN_ESCAPE_PATTERN, r"\\\1", text)


def _escape_link_target(value: str) -> str:
    return value.replace("\\", "\\\\").replace(")", "\\)")


def _inline_code_delimiter(text: str) -> str:
    max_run = 0
    for match in re.finditer("`+", text):
        max_run = max(max_run, len(match.group(0)))
    return "`" * max(1, max_run + 1)


def _render_inline_node(
    node: PageElement | None,
    *,
    code_language_resolver: Callable[[Tag], str],
) -> str:
    if isinstance(node, Comment | Declaration | Doctype | ProcessingInstruction):
        return ""
    if isinstance(node, NavigableString):
        return _escape_markdown_text(str(node))
    if not isinstance(node, Tag):
        return ""
    tag_name = str(node.name or "").lower()
    if tag_name in IGNORED_HTML_TAGS:
        return ""
    if tag_name == "br":
        return "\n"
    if tag_name == "code":
        code_text = node.get_text()
        if not code_text.strip():
            return ""
        delimiter = _inline_code_delimiter(code_text)
        return f"{delimiter}{code_text.strip()}{delimiter}"
    if tag_name in {"strong", "b"}:
        inner = render_inline_children(node, code_language_resolver=code_language_resolver)
        return f"**{inner}**" if inner else ""
    if tag_name in {"em", "i"}:
        inner = render_inline_children(node, code_language_resolver=code_language_resolver)
        return f"*{inner}*" if inner else ""
    if tag_name == "del":
        inner = render_inline_children(node, code_language_resolver=code_language_resolver)
        return f"~~{inner}~~" if inner else ""
    if tag_name == "a":
        link_text = render_inline_children(node, code_language_resolver=code_language_resolver)
        href = str(node.get("href") or "").strip()
        if not href:
            return link_text
        if not link_text:
            return href
        return f"[{link_text}]({_escape_link_target(href)})"
    if tag_name == "img":
        src = str(node.get("src") or "").strip()
        alt = _escape_markdown_text(str(node.get("alt") or "").strip())
        if not src:
            return alt
        return f"![{alt}]({_escape_link_target(src)})"
    return render_inline_children(node, code_language_resolver=code_language_resolver)
