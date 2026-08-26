"""SoAI - MCP news query construction [backend/mcp/tools/news_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from mcp.tools.argument_fields import optional_bounded_string, require_bounded_string
from mcp.tools.argument_scalars import parse_clamped_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.news_operator_mappings import (
    resolve_news_country_operator,
    resolve_news_language_operator,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("NewsRequest", "build_news_cache_key", "build_news_request", "build_news_url")

_TOP_HEADLINES_QUERIES: frozenset[str] = frozenset({"latest", "today"})
_DEFAULT_SEARCH_TIMESPAN = "24h"
_DEFAULT_LANGUAGE = "en"
_DEFAULT_COUNTRY = "US"
_DEFAULT_MAX_RESULTS = 10
_MIN_RESULTS_FLOOR = 10
_MAX_RESULTS_CEILING = 25
_MAX_QUERY_LENGTH = 500
_MAX_LANGUAGE_LENGTH = 64
_MAX_COUNTRY_LENGTH = 64


@dataclass(frozen=True, slots=True)
class NewsRequest:
    query: str
    language: str
    country: str
    max_results: int
    provider_query: str
    start_datetime: str | None
    end_datetime: str | None
    timespan: str | None
    top_headlines: bool
    target_date: date | None


def _has_date_shape(query: str) -> bool:
    return (
        len(query) == 10
        and query[4] == "-"
        and query[7] == "-"
        and query[0:4].isdigit()
        and query[5:7].isdigit()
        and query[8:10].isdigit()
    )


def _parse_date_query(query: str) -> date:
    try:
        return date.fromisoformat(query)
    except ValueError as exception:
        raise MCPToolError(-32602, f"Invalid date: {query}") from exception


def _build_provider_query(
    query: str,
    language_operator: str,
    country_operator: str,
    *,
    date_query: bool,
) -> str:
    filters = f"sourcecountry:{country_operator} sourcelang:{language_operator}"
    if query.strip().lower() in _TOP_HEADLINES_QUERIES:
        return filters
    if date_query:
        return filters
    return f"{query} {filters}"


def build_news_request(arguments: JSONDict) -> NewsRequest:
    query_value = get_arg(arguments, "query")
    language_value = arguments.get("language")
    country_value = arguments.get("country")
    query = require_bounded_string(
        query_value,
        field="query",
        max_length=_MAX_QUERY_LENGTH,
    )
    raw_language = (
        optional_bounded_string(
            language_value,
            field="language",
            max_length=_MAX_LANGUAGE_LENGTH,
        )
        or _DEFAULT_LANGUAGE
    )
    raw_country = (
        optional_bounded_string(
            country_value,
            field="country",
            max_length=_MAX_COUNTRY_LENGTH,
        )
        or _DEFAULT_COUNTRY
    )
    language, language_operator = resolve_news_language_operator(raw_language)
    country, country_operator = resolve_news_country_operator(raw_country)
    max_results = parse_clamped_int(
        arguments.get("max_results"),
        field_name="max_results",
        default=_DEFAULT_MAX_RESULTS,
        min_value=_MIN_RESULTS_FLOOR,
        max_value=_MAX_RESULTS_CEILING,
    )
    target_date: date | None = None
    if _has_date_shape(query):
        target_date = _parse_date_query(query)
    top_headlines = query.strip().lower() in _TOP_HEADLINES_QUERIES
    return NewsRequest(
        query=query,
        language=language,
        country=country,
        max_results=max_results,
        provider_query=_build_provider_query(
            query,
            language_operator,
            country_operator,
            date_query=target_date is not None,
        ),
        start_datetime=f"{target_date:%Y%m%d}000000" if target_date is not None else None,
        end_datetime=f"{target_date:%Y%m%d}235959" if target_date is not None else None,
        timespan=None if target_date is not None else _DEFAULT_SEARCH_TIMESPAN,
        top_headlines=top_headlines,
        target_date=target_date,
    )


def build_news_cache_key(request: NewsRequest) -> str:
    return "|".join(
        (
            request.query,
            request.provider_query,
            str(request.max_results),
            request.start_datetime or "",
            request.end_datetime or "",
            request.timespan or "",
            str(request.top_headlines),
            request.target_date.isoformat() if request.target_date is not None else "",
        )
    )


def build_news_url(base_url: str, request: NewsRequest) -> str:
    params: dict[str, str] = {
        "query": request.provider_query,
        "mode": "ArtList",
        "format": "json",
        "sort": "DateDesc",
        "maxrecords": str(request.max_results),
    }
    if request.timespan is not None:
        params["timespan"] = request.timespan
    if request.start_datetime is not None and request.end_datetime is not None:
        params["startdatetime"] = request.start_datetime
        params["enddatetime"] = request.end_datetime
    return f"{base_url}/doc?{urlencode(params)}"
