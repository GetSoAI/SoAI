"""SoAI - MCP utility tool definition: news [backend/mcp/tools/utility_tool_definitions/news.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import (
    build_title_property_schema,
    build_tool_annotation_flags,
    build_tool_icon_entry,
)
from mcp.tools.icons import ICON_NEWS
from mcp.tools.news_payload import (
    NEWS_SEARCH_MODE_FULLTEXT_COUNTRY,
    NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL,
)
from mcp.tools.utility_tool_definitions.schema_fragments import (
    build_object_input_schema,
    build_required_query_property,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_news_tool_definitions",)


def build_news_tool_definitions() -> dict[str, JSONDict]:
    return {
        "news": {
            "title": "News",
            "description": (
                "Search recent image-capable news articles through GDELT. DOC 2.0 provides "
                "full-text country-filtered results; the official Article List provides a "
                "global headline-and-summary fallback when DOC is unavailable. Use 'latest' "
                "or 'today' for current headlines, a date in YYYY-MM-DD format for articles "
                "from a specific day, or any keyword or phrase for news search."
            ),
            "icons": [build_tool_icon_entry(ICON_NEWS)],
            "input_schema": build_object_input_schema(
                properties={
                    "query": {
                        **build_required_query_property(
                            description=(
                                "Search query: 'latest' or 'today', a date in YYYY-MM-DD "
                                "format, or a keyword/phrase."
                            ),
                            max_length=500,
                        ),
                    },
                    "language": {
                        "type": "string",
                        "maxLength": 64,
                        "description": "Language code or name. Defaults to en.",
                    },
                    "country": {
                        "type": "string",
                        "maxLength": 64,
                        "description": "Country code or name. Defaults to US.",
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 10,
                        "maximum": 25,
                        "description": "Maximum number of articles to return. Values below 10 are raised to 10. Defaults to 10.",
                    },
                },
                required=["query"],
            ),
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "query",
                    "language",
                    "country",
                    "requested_country",
                    "search_mode",
                    "articles",
                    "article_count",
                ],
                "properties": {
                    "query": {"type": "string"},
                    "language": {"type": "string"},
                    "country": {"type": "string"},
                    "requested_country": {"type": "string"},
                    "search_mode": {
                        "type": "string",
                        "enum": [
                            NEWS_SEARCH_MODE_FULLTEXT_COUNTRY,
                            NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL,
                        ],
                    },
                    "articles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["title", "url", "source", "published", "image"],
                            "properties": {
                                **build_title_property_schema(),
                                "url": {"type": "string"},
                                "source": {"type": "string"},
                                "published": {"type": "string"},
                                "image": {"type": "string"},
                            },
                        },
                    },
                    "article_count": {"type": "integer"},
                },
            },
            "annotations": {
                **build_tool_annotation_flags(read_only=True, open_world=True),
                "requiresApprovalHint": False,
            },
        },
    }
