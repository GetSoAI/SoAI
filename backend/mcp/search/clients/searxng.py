"""SoAI - SearXNG search client [backend/mcp/search/clients/searxng.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

import httpx2

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.validation.string_sequences import normalize_delimited_string_sequence
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.models import SearchResult

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from mcp.search.clients.client_base import QueryParamScalar

__all__ = ("SearXNGSearchClient",)


class SearXNGSearchClient(SearchClientBase):
    PROVIDER_NAME = "searxng"

    def __init__(
        self,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        http_client: httpx2.AsyncClient,
        api_key_resolver: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        super().__init__(config, runtime_flags, http_client, api_key_resolver=api_key_resolver)
        self.base_url = config.require_str_value("TOOLS.RAG.SEARXNG.BASE_URL").strip()
        self.default_engines = normalize_delimited_string_sequence(
            config.get("TOOLS.RAG.SEARXNG.ENGINES"),
            label="TOOLS.RAG.SEARXNG.ENGINES",
        )
        self.default_categories = normalize_delimited_string_sequence(
            config.get("TOOLS.RAG.SEARXNG.DEFAULT_CATEGORIES"),
            label="TOOLS.RAG.SEARXNG.DEFAULT_CATEGORIES",
        )

    @override
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **search_options: JSONValue,
    ) -> list[SearchResult]:
        query = self._prepare_search_query(query, source="SearXNG web search")
        if not self.base_url:
            raise ValidationError("TOOLS.RAG.SEARXNG.BASE_URL is not configured")
        categories = search_options.pop("categories", None)
        engines = search_options.pop("engines", None)
        default_categories = ",".join(self.default_categories)
        default_engines = ",".join(self.default_engines)
        params: dict[str, QueryParamScalar] = {
            "q": query,
            "format": "json",
            "categories": (
                categories if isinstance(categories, str) and categories else default_categories
            ),
        }
        if engines or default_engines:
            params["engines"] = engines if isinstance(engines, str) and engines else default_engines
        data = await self._request(
            "GET",
            f"{self.base_url.rstrip('/')}/search",
            params=params,
            query=query,
        )
        payload = self._require_json_dict(data, error_message="Unexpected SearXNG response format.")
        return self._build_search_results(
            self._coerce_search_items(payload.get("results")),
            source=self.PROVIDER_NAME,
            title_key="title",
            snippet_key="content",
            url_key="url",
            max_results=max_results,
        )
