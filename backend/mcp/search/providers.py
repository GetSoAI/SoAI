"""SoAI - MCP search provider registry [backend/mcp/search/providers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from mcp.search.clients.brave import BraveSearchClient
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.clients.duckduckgo import DuckDuckGoSearchClient
from mcp.search.clients.google import GoogleCustomSearchClient
from mcp.search.clients.searxng import SearXNGSearchClient
from mcp.search.clients.serper import SerperSearchClient
from mcp.search.clients.tavily import TavilySearchClient

__all__ = (
    "SearchProviderSpec",
    "get_search_provider_specs",
    "get_search_providers",
    "has_search_provider",
    "list_supported_providers",
    "normalize_search_provider_name",
    "resolve_search_provider_class",
)


@dataclass(frozen=True, slots=True)
class SearchProviderSpec:
    provider_name: str
    client_class: type[SearchClientBase]
    tool_title: str
    tool_description: str
    handler_source: str
    string_arguments: tuple[str, ...]
    list_arguments: tuple[str, ...]
    input_properties: tuple[
        tuple[str, dict[str, str | int | bool | list[str] | dict[str, str | int]]],
        ...,
    ]


@lru_cache(maxsize=1)
def get_search_provider_specs() -> tuple[SearchProviderSpec, ...]:
    return (
        SearchProviderSpec(
            provider_name="duckduckgo",
            client_class=DuckDuckGoSearchClient,
            tool_title="Search DuckDuckGo",
            tool_description=(
                "Search using DuckDuckGo. Free, no API key required. Privacy-focused "
                "search with results from DuckDuckGo's index."
            ),
            handler_source="DuckDuckGo",
            string_arguments=("region",),
            list_arguments=(),
            input_properties=(
                (
                    "region",
                    {
                        "type": "string",
                        "description": "Region code for results (default us-en)",
                    },
                ),
            ),
        ),
        SearchProviderSpec(
            provider_name="searxng",
            client_class=SearXNGSearchClient,
            tool_title="Search SearXNG",
            tool_description=(
                "Search using a self-hosted SearXNG metasearch instance. Aggregates results "
                "from multiple search engines. Requires TOOLS.RAG.SEARXNG.BASE_URL configuration."
            ),
            handler_source="SearXNG",
            string_arguments=("categories", "engines"),
            list_arguments=(),
            input_properties=(
                (
                    "categories",
                    {
                        "type": "string",
                        "description": "Search categories (default general)",
                    },
                ),
                (
                    "engines",
                    {
                        "type": "string",
                        "description": "Comma-separated list of engines to use",
                    },
                ),
            ),
        ),
        SearchProviderSpec(
            provider_name="brave",
            client_class=BraveSearchClient,
            tool_title="Search Brave",
            tool_description=(
                "Search using Brave Search API. Privacy-focused search with independent index. "
                "Requires a configured Brave Search API key."
            ),
            handler_source="Brave",
            string_arguments=("country", "search_lang", "freshness"),
            list_arguments=(),
            input_properties=(
                (
                    "country",
                    {"type": "string", "description": "Country code for results (default us)"},
                ),
                (
                    "search_lang",
                    {"type": "string", "description": "Search language (default en)"},
                ),
                (
                    "freshness",
                    {
                        "type": "string",
                        "description": (
                            "Freshness filter: pd (past day), pw (past week), "
                            "pm (past month), py (past year)"
                        ),
                    },
                ),
            ),
        ),
        SearchProviderSpec(
            provider_name="tavily",
            client_class=TavilySearchClient,
            tool_title="Search Tavily",
            tool_description=(
                "AI-optimized search using Tavily API. Designed for LLM and RAG applications. "
                "Requires a configured Tavily API key."
            ),
            handler_source="Tavily",
            string_arguments=("search_depth",),
            list_arguments=("include_domains", "exclude_domains"),
            input_properties=(
                (
                    "search_depth",
                    {
                        "type": "string",
                        "description": "Search depth: basic or advanced (default basic)",
                    },
                ),
                (
                    "include_domains",
                    {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Only include results from these domains",
                    },
                ),
                (
                    "exclude_domains",
                    {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exclude results from these domains",
                    },
                ),
            ),
        ),
        SearchProviderSpec(
            provider_name="serper",
            client_class=SerperSearchClient,
            tool_title="Search Serper",
            tool_description=(
                "Search using Serper.dev Google SERP API. Returns Google search results. "
                "Requires a configured Serper API key."
            ),
            handler_source="Serper",
            string_arguments=("gl", "hl"),
            list_arguments=(),
            input_properties=(
                ("gl", {"type": "string", "description": "Geolocation code (default us)"}),
                ("hl", {"type": "string", "description": "Language code (default en)"}),
            ),
        ),
        SearchProviderSpec(
            provider_name="google",
            client_class=GoogleCustomSearchClient,
            tool_title="Search Google",
            tool_description=(
                "Search using Google Custom Search JSON API. 100 free queries/day. Requires "
                "a configured Google API key and TOOLS.RAG.GOOGLE.SEARCH_ENGINE_ID."
            ),
            handler_source="Google Custom Search",
            string_arguments=("safe",),
            list_arguments=(),
            input_properties=(
                (
                    "safe",
                    {
                        "type": "string",
                        "description": "Safe search level: off, medium, high (default off)",
                    },
                ),
            ),
        ),
    )


@lru_cache(maxsize=1)
def get_search_providers() -> tuple[tuple[str, type[SearchClientBase]], ...]:
    return tuple(
        (provider.provider_name, provider.client_class) for provider in get_search_provider_specs()
    )


def _active_search_providers(
    search_providers: tuple[tuple[str, type[SearchClientBase]], ...] | None = None,
) -> tuple[tuple[str, type[SearchClientBase]], ...]:
    return search_providers or get_search_providers()


def list_supported_providers(
    search_providers: tuple[tuple[str, type[SearchClientBase]], ...] | None = None,
) -> list[str]:
    active_search_providers = _active_search_providers(search_providers)
    return sorted(name for name, _provider_cls in active_search_providers)


def has_search_provider(
    provider_name: str | None,
    search_providers: tuple[tuple[str, type[SearchClientBase]], ...] | None = None,
) -> bool:
    return resolve_search_provider_class(provider_name, search_providers) is not None


def resolve_search_provider_class(
    provider_name: str | None,
    search_providers: tuple[tuple[str, type[SearchClientBase]], ...] | None = None,
) -> type[SearchClientBase] | None:
    normalized = normalize_search_provider_name(provider_name, search_providers)
    if not normalized:
        return None
    active_search_providers = _active_search_providers(search_providers)
    for configured_provider_name, provider_class in active_search_providers:
        if configured_provider_name.lower() == normalized:
            return provider_class
    return None


def normalize_search_provider_name(
    provider_name: str | None,
    search_providers: tuple[tuple[str, type[SearchClientBase]], ...] | None = None,
) -> str:
    if provider_name is None:
        return ""
    normalized = provider_name.strip().lower()
    if not normalized:
        return ""
    active_search_providers = _active_search_providers(search_providers)
    for configured_provider_name, _provider_class in active_search_providers:
        if configured_provider_name.lower() == normalized:
            return configured_provider_name
    return normalized
