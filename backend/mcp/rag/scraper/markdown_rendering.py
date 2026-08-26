"""SoAI - Internal HTML-to-Markdown renderer [backend/mcp/rag/scraper/markdown_rendering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from bs4 import BeautifulSoup, Tag

from mcp.rag.scraper.markdown_inline import (
    IGNORED_HTML_TAGS,
    code_fence,
    escape_table_cell,
    indent_block,
    normalize_document_markdown,
    normalize_inline_whitespace,
    render_inline_children,
    render_inline_fragment,
)

__all__ = ("render_html_fragment_to_markdown",)

_CONTAINER_TAGS: frozenset[str] = frozenset(
    {"html", "body", "main", "article", "section", "div", "header", "footer", "aside"},
)
_BLOCK_TAGS: frozenset[str] = frozenset(
    {
        "html",
        "body",
        "main",
        "article",
        "section",
        "div",
        "header",
        "footer",
        "aside",
        "p",
        "pre",
        "blockquote",
        "ul",
        "ol",
        "table",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    },
)


def _render_heading(node: Tag, code_language_resolver: Callable[[Tag], str]) -> str:
    tag_name = str(node.name or "").lower()
    level = int(tag_name[1]) if len(tag_name) == 2 and tag_name[1].isdigit() else 1
    text = render_inline_children(node, code_language_resolver=code_language_resolver)
    if not text:
        return ""
    return f"{'#' * level} {text}"


def _render_preformatted(node: Tag, code_language_resolver: Callable[[Tag], str]) -> str:
    code_node = node.find("code")
    source_node = code_node if isinstance(code_node, Tag) else node
    code_text = source_node.get_text().strip("\n")
    if not code_text.strip():
        return ""
    language = code_language_resolver(source_node)
    fence = code_fence(code_text)
    opening = fence + language if language else fence
    return f"{opening}\n{code_text}\n{fence}"


def _render_table(node: Tag, code_language_resolver: Callable[[Tag], str]) -> str:
    rows: list[list[str]] = []
    for row in node.find_all("tr"):
        cells = row.find_all(("th", "td"), recursive=False)
        if not cells:
            continue
        rendered_row = [
            escape_table_cell(
                render_inline_children(
                    cell,
                    code_language_resolver=code_language_resolver,
                ),
            )
            for cell in cells
        ]
        rows.append(rendered_row)
    if not rows:
        return ""
    column_count = max(len(row) for row in rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in rows]
    header = padded_rows[0]
    body = padded_rows[1:]
    separator = ["---"] * column_count
    lines = [
        f"| {' | '.join(header)} |",
        f"| {' | '.join(separator)} |",
    ]
    for rendered_row in body:
        lines.append(f"| {' | '.join(rendered_row)} |")
    return "\n".join(lines)


def _render_list_item(
    node: Tag,
    marker: str,
    code_language_resolver: Callable[[Tag], str],
) -> str:
    blocks = _render_block_children(node, code_language_resolver)
    if not blocks:
        return marker.rstrip()
    first_block_lines = blocks[0].splitlines()
    lines: list[str]
    if _starts_with_nested_list(node, code_language_resolver):
        lines = [marker.rstrip()]
        for line in first_block_lines:
            lines.append((f"  {line}") if line else "")
    else:
        lines = [marker + first_block_lines[0]]
        for line in first_block_lines[1:]:
            lines.append((f"  {line}") if line else "")
    for block in blocks[1:]:
        indented = indent_block(block)
        if indented:
            lines.append(indented)
    return "\n".join(lines)


def _render_list(node: Tag, code_language_resolver: Callable[[Tag], str]) -> str:
    rendered_items: list[str] = []
    is_ordered = str(node.name or "").lower() == "ol"
    item_index = _resolve_list_start(node) if is_ordered else 1
    for child in node.children:
        if not isinstance(child, Tag) or str(child.name or "").lower() != "li":
            continue
        marker = f"{item_index}. " if is_ordered else "- "
        item = _render_list_item(child, marker, code_language_resolver)
        if item:
            rendered_items.append(item)
        if is_ordered:
            item_index += 1
    return "\n".join(rendered_items)


def _render_blockquote(node: Tag, code_language_resolver: Callable[[Tag], str]) -> str:
    rendered = "\n\n".join(_render_block_children(node, code_language_resolver))
    if not rendered:
        return ""
    return "\n".join((f"> {line}") if line else ">" for line in rendered.splitlines())


def _resolve_list_start(node: Tag) -> int:
    start_value = node.get("start")
    if isinstance(start_value, bool) or start_value is None:
        return 1
    if not isinstance(start_value, str):
        return 1
    try:
        parsed = int(start_value)
    except (TypeError, ValueError):
        return 1
    return max(parsed, 1)


def _starts_with_nested_list(
    node: Tag,
    code_language_resolver: Callable[[Tag], str],
) -> bool:
    for child in node.children:
        if not isinstance(child, Tag):
            if render_inline_fragment(
                child,
                code_language_resolver=code_language_resolver,
            ).strip():
                return False
            continue
        tag_name = str(child.name or "").lower()
        if tag_name in IGNORED_HTML_TAGS:
            continue
        return tag_name in {"ul", "ol"}
    return False


def _render_block_children(
    node: Tag | BeautifulSoup,
    code_language_resolver: Callable[[Tag], str],
) -> list[str]:
    blocks: list[str] = []
    inline_fragments: list[str] = []
    for child in node.children:
        if not isinstance(child, Tag):
            inline_fragments.append(
                render_inline_fragment(
                    child,
                    code_language_resolver=code_language_resolver,
                ),
            )
            continue
        tag_name = str(child.name or "").lower()
        if tag_name in IGNORED_HTML_TAGS:
            continue
        if tag_name in _BLOCK_TAGS:
            inline_block = normalize_inline_whitespace("".join(inline_fragments))
            if inline_block:
                blocks.append(inline_block)
            inline_fragments = []
            rendered = _render_block_node(child, code_language_resolver)
            if rendered:
                blocks.append(rendered)
            continue
        inline_fragments.append(
            render_inline_fragment(
                child,
                code_language_resolver=code_language_resolver,
            ),
        )
    inline_block = normalize_inline_whitespace("".join(inline_fragments))
    if inline_block:
        blocks.append(inline_block)
    return blocks


def _render_block_node(node: Tag, code_language_resolver: Callable[[Tag], str]) -> str:
    tag_name = str(node.name or "").lower()
    if tag_name in _CONTAINER_TAGS:
        return "\n\n".join(_render_block_children(node, code_language_resolver))
    if tag_name == "p":
        return render_inline_children(node, code_language_resolver=code_language_resolver)
    if tag_name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return _render_heading(node, code_language_resolver)
    if tag_name == "pre":
        return _render_preformatted(node, code_language_resolver)
    if tag_name in {"ul", "ol"}:
        return _render_list(node, code_language_resolver)
    if tag_name == "blockquote":
        return _render_blockquote(node, code_language_resolver)
    if tag_name == "table":
        return _render_table(node, code_language_resolver)
    if tag_name == "hr":
        return "---"
    return render_inline_children(node, code_language_resolver=code_language_resolver)


def render_html_fragment_to_markdown(
    html_str: str,
    *,
    code_language_resolver: Callable[[Tag], str],
) -> str:
    soup = BeautifulSoup(html_str, "html.parser")
    rendered = "\n\n".join(_render_block_children(soup, code_language_resolver))
    return normalize_document_markdown(rendered)
