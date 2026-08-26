"""SoAI - DuckDuckGo search client via ddgs library [backend/mcp/search/clients/duckduckgo.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

import httpx2
from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.runtime.protocols import RuntimeFlagsViewProtocol
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.models import SearchResult

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("DuckDuckGoSearchClient",)

LOGGER_NAME = "SoAI.mcp.search.duckduckgo"


class DuckDuckGoSearchClient(SearchClientBase):
    PROVIDER_NAME = "duckduckgo"

    def __init__(
        self,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        http_client: httpx2.AsyncClient,
        api_key_resolver: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        super().__init__(config, runtime_flags, http_client, api_key_resolver=api_key_resolver)
        self._backend = config.require_str("TOOLS.RAG.DUCKDUCKGO.BACKEND")
        self._proxy = config.require_str_value("TOOLS.RAG.DUCKDUCKGO.PROXY")
        self._ddgs_timeout = max(1, int(config.get_int("TOOLS.RAG.DUCKDUCKGO.TIMEOUT")))

    @override
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **search_options: JSONValue,
    ) -> list[SearchResult]:
        query = self._prepare_search_query(query, source="DuckDuckGo web search")
        region = search_options.pop("region", None)
        effective_region = region if isinstance(region, str) and region.strip() else "us-en"
        effective_max = min(max(1, max_results), 50)
        raw_results = await self._execute_search(query, effective_max, effective_region)
        results: list[SearchResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            href = item.get("href", "")
            body = item.get("body", "")
            results.append(
                SearchResult(
                    title if isinstance(title, str) else "",
                    body if isinstance(body, str) else "",
                    href if isinstance(href, str) else "",
                    self.PROVIDER_NAME,
                ),
            )
        return results

    async def _execute_search(
        self,
        query: str,
        max_results: int,
        region: str,
    ) -> list[dict[str, str]]:
        logger = get_logger(LOGGER_NAME)
        proxy = self._proxy or None

        def _run_search() -> list[dict[str, str]]:
            with DDGS(proxy=proxy, timeout=self._ddgs_timeout) as ddgs_client:
                return ddgs_client.text(
                    query,
                    region=region,
                    max_results=max_results,
                    backend=self._backend,
                )

        try:
            return await asyncio.to_thread(_run_search)
        except RatelimitException as exception:
            logger.warning("DuckDuckGo rate limit hit for query: %s", query[:80])
            raise ValidationError(
                "DuckDuckGo rate limit reached. Please wait a moment before searching again.",
            ) from exception
        except TimeoutException as exception:
            logger.warning("DuckDuckGo search timed out for query: %s", query[:80])
            raise ValidationError(
                f"DuckDuckGo search timed out after {self._ddgs_timeout}s.",
            ) from exception
        except DDGSException as exception:
            logger.warning(
                "DuckDuckGo search error for query '%s': %s",
                query[:80],
                str(exception),
            )
            raise ValidationError(f"DuckDuckGo search failed: {exception}") from exception
