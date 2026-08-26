"""SoAI - Google Custom Search client [backend/mcp/search/clients/google.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

import httpx2

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.runtime.protocols import RuntimeFlagsViewProtocol
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.models import SearchResult

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from mcp.search.clients.client_base import QueryParamScalar

__all__ = ("GoogleCustomSearchClient",)


class GoogleCustomSearchClient(SearchClientBase):
    PROVIDER_NAME = "google"

    def __init__(
        self,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        http_client: httpx2.AsyncClient,
        api_key_resolver: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        super().__init__(config, runtime_flags, http_client, api_key_resolver=api_key_resolver)
        self.search_engine_id = config.require_str_value(
            "TOOLS.RAG.GOOGLE.SEARCH_ENGINE_ID",
        ).strip()
        self.default_safe = config.require_str("TOOLS.RAG.GOOGLE.DEFAULT_SAFE")

    async def _fetch_google_page(
        self,
        api_key: str,
        query: str,
        start_index: int,
        number: int,
        safe: str,
    ) -> list[SearchResult]:
        params: dict[str, QueryParamScalar] = {
            "key": api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": number,
            "start": start_index,
            "safe": safe,
        }
        data = await self._request(
            "GET",
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            query=query,
        )
        payload = self._require_json_dict(
            data,
            error_message="Unexpected Google Custom Search response format.",
        )
        return [
            self._build_search_result(
                item,
                source=self.PROVIDER_NAME,
                title_key="title",
                snippet_key="snippet",
                url_key="link",
            )
            for item in self._coerce_search_items(payload.get("items"))
        ]

    @override
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **search_options: JSONValue,
    ) -> list[SearchResult]:
        safe_value = search_options.pop("safe", None)
        safe = safe_value if isinstance(safe_value, str) else None
        query = self._prepare_search_query(query, source="Google Custom Search")
        api_key = await self._require_api_key()
        if not self.search_engine_id:
            raise ValidationError("TOOLS.RAG.GOOGLE.SEARCH_ENGINE_ID is not configured")
        effective_safe = safe or self.default_safe
        all_results: list[SearchResult] = []
        start_index = 1
        while len(all_results) < max_results:
            page_size = min(max_results - len(all_results), 10)
            page_results = await self._fetch_google_page(
                api_key,
                query,
                start_index,
                page_size,
                effective_safe,
            )
            if not page_results:
                break
            all_results.extend(page_results)
            if len(page_results) < page_size:
                break
            start_index += len(page_results)
        return all_results[:max_results]
