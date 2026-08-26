"""SoAI - MCP search result models [backend/mcp/search/models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("SearchResult",)


@dataclass(slots=True)
class SearchResult:
    title: str
    snippet: str
    url: str
    source: str
