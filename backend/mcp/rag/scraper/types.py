"""SoAI - MCP web scraper type definitions [backend/mcp/rag/scraper/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("FetchedContent",)

HTML_TYPES = frozenset(("text/html", "application/xhtml+xml"))
MARKDOWN_TYPES = frozenset(("text/markdown",))
JSON_TYPES = frozenset(("application/json", "text/json"))
XML_TYPES = frozenset(
    ("application/xml", "text/xml", "application/rss+xml", "application/atom+xml"),
)


@dataclass(frozen=True, slots=True)
class FetchedContent:
    content: str
    content_type: str
    title: str | None = None
    page_count: int | None = None
    source_url: str | None = None
    source_html: str | None = None
