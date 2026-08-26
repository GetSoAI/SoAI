"""SoAI - Brave search client [backend/mcp/search/clients/brave.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

import httpx2

from core.config.protocols import ConfigProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.models import SearchResult

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from mcp.search.clients.client_base import QueryParamScalar

__all__ = ("BraveSearchClient",)


class BraveSearchClient(SearchClientBase):
    PROVIDER_NAME = "brave"

    def __init__(
        self,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        http_client: httpx2.AsyncClient,
        api_key_resolver: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        super().__init__(config, runtime_flags, http_client, api_key_resolver=api_key_resolver)
        self.default_country = config.require_str("TOOLS.RAG.BRAVE.DEFAULT_COUNTRY").lower()
        self.default_search_lang = config.require_str("TOOLS.RAG.BRAVE.DEFAULT_SEARCH_LANG").lower()

    @override
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **search_options: JSONValue,
    ) -> list[SearchResult]:
        query = self._prepare_search_query(query, source="Brave web search")
        api_key = await self._require_api_key()
        country_value = search_options.pop("country", None)
        search_lang_value = search_options.pop("search_lang", None)
        freshness_value = search_options.pop("freshness", None)
        params: dict[str, QueryParamScalar] = {
            "q": query,
            "count": min(max_results, 20),
            "country": (country_value if isinstance(country_value, str) else self.default_country),
            "search_lang": (
                search_lang_value
                if isinstance(search_lang_value, str)
                else self.default_search_lang
            ),
        }
        if isinstance(freshness_value, str):
            params["freshness"] = freshness_value
        data = await self._request(
            "GET",
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params=params,
            query=query,
        )
        payload = self._require_json_dict(
            data,
            error_message="Unexpected Brave search response format.",
        )
        web_value = payload.get("web")
        if not isinstance(web_value, dict):
            return []
        return [
            self._build_search_result(
                result,
                source=self.PROVIDER_NAME,
                title_key="title",
                snippet_key="description",
                url_key="url",
            )
            for result in self._coerce_search_items(web_value.get("results"))[:max_results]
        ]
