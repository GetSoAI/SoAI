"""SoAI - Serper search client [backend/mcp/search/clients/serper.py]"""
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

__all__ = ("SerperSearchClient",)


class SerperSearchClient(SearchClientBase):
    PROVIDER_NAME = "serper"

    def __init__(
        self,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        http_client: httpx2.AsyncClient,
        api_key_resolver: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        super().__init__(config, runtime_flags, http_client, api_key_resolver=api_key_resolver)
        self.default_gl = config.require_str("TOOLS.RAG.SERPER.DEFAULT_GL")
        self.default_hl = config.require_str("TOOLS.RAG.SERPER.DEFAULT_HL")

    @override
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **search_options: JSONValue,
    ) -> list[SearchResult]:
        query = self._prepare_search_query(query, source="Serper web search")
        gl = search_options.pop("gl", None)
        hl = search_options.pop("hl", None)
        api_key = await self._require_api_key()
        payload: dict[str, JSONValue] = {
            "q": query,
            "gl": gl if isinstance(gl, str) and gl else self.default_gl,
            "hl": hl if isinstance(hl, str) and hl else self.default_hl,
            "num": min(max_results, 100),
        }
        data = await self._request(
            "POST",
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json_payload=payload,
            query=query,
        )
        response = self._require_json_dict(data, error_message="Unexpected Serper response format.")
        return [
            self._build_search_result(
                result,
                source=self.PROVIDER_NAME,
                title_key="title",
                snippet_key="snippet",
                url_key="link",
            )
            for result in self._coerce_search_items(response.get("organic"))[:max_results]
        ]
