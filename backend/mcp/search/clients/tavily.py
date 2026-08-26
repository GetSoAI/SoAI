"""SoAI - Tavily search client [backend/mcp/search/clients/tavily.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

import httpx2

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import is_str_list
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.models import SearchResult

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("TavilySearchClient",)


class TavilySearchClient(SearchClientBase):
    PROVIDER_NAME = "tavily"

    def __init__(
        self,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        http_client: httpx2.AsyncClient,
        api_key_resolver: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        super().__init__(config, runtime_flags, http_client, api_key_resolver=api_key_resolver)
        self.default_search_depth = config.require_str("TOOLS.RAG.TAVILY.DEFAULT_SEARCH_DEPTH")
        self.include_answer = config.get_bool("TOOLS.RAG.TAVILY.INCLUDE_ANSWER")

    @override
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **search_options: JSONValue,
    ) -> list[SearchResult]:
        query = self._prepare_search_query(query, source="Tavily web search")
        search_depth = search_options.pop("search_depth", None)
        include_domains = search_options.pop("include_domains", None)
        exclude_domains = search_options.pop("exclude_domains", None)
        api_key = await self._require_api_key()
        resolved_search_depth = (
            search_depth.strip()
            if isinstance(search_depth, str) and search_depth.strip()
            else self.default_search_depth
        )
        payload: dict[str, JSONValue] = {
            "api_key": api_key,
            "query": query,
            "search_depth": resolved_search_depth,
            "max_results": max_results,
            "include_answer": self.include_answer,
        }
        if include_domains is not None:
            if not is_str_list(include_domains):
                raise ValidationError("include_domains must be a list of strings.")
            if include_domains:
                payload["include_domains"] = include_domains
        if exclude_domains is not None:
            if not is_str_list(exclude_domains):
                raise ValidationError("exclude_domains must be a list of strings.")
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains
        data = await self._request(
            "POST",
            "https://api.tavily.com/search",
            json_payload=payload,
            query=query,
        )
        payload = self._require_json_dict(data, error_message="Unexpected Tavily response format.")
        items = self._coerce_search_items(payload.get("results"))
        return self._build_search_results(
            items,
            source=self.PROVIDER_NAME,
            title_key="title",
            snippet_key="content",
            url_key="url",
            max_results=max_results,
        )
