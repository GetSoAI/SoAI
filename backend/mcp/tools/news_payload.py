"""SoAI - MCP news result payload normalization [backend/mcp/tools/news_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict
from mcp.tools.news_query import NewsRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NEWS_SEARCH_MODE_FULLTEXT_COUNTRY",
    "NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL",
    "build_news_result_payload",
)

_GDELT_DATE_LENGTH = 16
NEWS_SEARCH_MODE_FULLTEXT_COUNTRY = "fulltext_country"
NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL = "headline_summary_global"


def _normalize_gdelt_seen_date(value: str) -> str:
    stripped = value.strip()
    if (
        len(stripped) == _GDELT_DATE_LENGTH
        and stripped[8] == "T"
        and stripped[15] == "Z"
        and stripped[:8].isdigit()
        and stripped[9:15].isdigit()
    ):
        return (
            f"{stripped[0:4]}-{stripped[4:6]}-{stripped[6:8]}"
            f"T{stripped[9:11]}:{stripped[11:13]}:{stripped[13:15]}Z"
        )
    return stripped


def _json_string(value: JSONValue | None) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _build_article(entry: JSONDict) -> JSONDict | None:
    url = _json_string(entry.get("url"))
    if not url:
        return None
    return {
        "title": _json_string(entry.get("title")),
        "url": url,
        "source": _json_string(entry.get("domain")),
        "published": _normalize_gdelt_seen_date(_json_string(entry.get("seendate"))),
        "image": _json_string(entry.get("socialimage")),
    }


def build_news_result_payload(
    request: NewsRequest,
    provider_payload: JSONDict,
    *,
    effective_country: str,
    search_mode: str,
) -> JSONDict:
    raw_articles = provider_payload.get("articles")
    articles: list[JSONDict] = []
    if isinstance(raw_articles, list):
        for raw_article in raw_articles:
            article_entry = coerce_json_dict(raw_article)
            if article_entry is None:
                continue
            article = _build_article(article_entry)
            if article is not None:
                articles.append(article)
            if len(articles) >= request.max_results:
                break
    return {
        "query": request.query,
        "language": request.language,
        "country": effective_country,
        "requested_country": request.country,
        "search_mode": search_mode,
        "articles": articles,
        "article_count": len(articles),
    }
