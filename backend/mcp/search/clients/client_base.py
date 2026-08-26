"""SoAI - MCP search provider base class with retries [backend/mcp/search/clients/client_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING, NoReturn

import httpx2

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from core.network.http_json import read_http_json_value
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.types.json import is_json_dict
from core.types.json_value import filter_json_dict_list
from mcp.search.models import SearchResult
from mcp.tools.offline_policy import build_offline_mode_error

if TYPE_CHECKING:
    from core.types.json import JSONValue

    type QueryParamScalar = str | int | float | bool | None
    type QueryParamValue = QueryParamScalar | Sequence[QueryParamScalar]
    type QueryParamsInput = (
        httpx2.QueryParams
        | Mapping[str, QueryParamValue]
        | list[tuple[str, QueryParamScalar]]
        | tuple[tuple[str, QueryParamScalar], ...]
        | str
        | bytes
    )
    type HeadersInput = dict[str, str] | httpx2.Headers

__all__ = ("SearchClientBase",)

LOGGER_NAME = "SoAI.mcp.search.client_base"


class SearchClientBase:
    PROVIDER_NAME = "base"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        **search_options: JSONValue,
    ) -> list[SearchResult]:
        _ = query
        _ = max_results
        _ = search_options
        raise StateError("Subclasses must implement search().")

    def __init__(
        self,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        http_client: httpx2.AsyncClient,
        api_key_resolver: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        self.config = config
        self.runtime_flags = runtime_flags
        self.http_client = http_client
        self._api_key_resolver = api_key_resolver
        self.timeout = max(1, int(config.get_int("TOOLS.RAG.WEB.REQUEST_TIMEOUT")))
        self.max_retries = min(
            10,
            max(
                1,
                int(config.get_int("TOOLS.RAG.WEB.SEARCH_RETRY_ATTEMPTS")),
            ),
        )
        self.retry_delay = max(0, int(config.get_int("TOOLS.RAG.WEB.SEARCH_RETRY_DELAY")))

    async def _get_api_key(self) -> str:
        if self._api_key_resolver:
            api_key = await self._api_key_resolver(self.PROVIDER_NAME)
            if api_key:
                return api_key
        return ""

    async def _require_api_key(self) -> str:
        api_key = await self._get_api_key()
        if not api_key:
            raise ValidationError(
                f"Search provider API key is not configured for {self.PROVIDER_NAME}.",
            )
        return api_key

    def _prepare_search_query(self, query: str, source: str) -> str:
        if self.runtime_flags.offline_mode:
            raise build_offline_mode_error(
                tool_name=f"web_search_{self.PROVIDER_NAME}",
                capability=source,
                url=None,
            )
        normalized_query = query.strip()
        if not normalized_query:
            raise ValidationError("Search query cannot be empty")
        return normalized_query

    @staticmethod
    def _require_json_dict(
        payload: JSONValue,
        *,
        error_message: str,
    ) -> dict[str, JSONValue]:
        if not is_json_dict(payload):
            raise ValidationError(error_message)
        return payload

    @staticmethod
    def _coerce_search_items(value: JSONValue) -> list[dict[str, JSONValue]]:
        return filter_json_dict_list(value)

    @staticmethod
    def _text_or_empty(value: JSONValue | None) -> str:
        return value if isinstance(value, str) else ""

    @staticmethod
    def _build_search_result(
        item: dict[str, JSONValue],
        *,
        source: str,
        title_key: str,
        snippet_key: str,
        url_key: str,
    ) -> SearchResult:
        return SearchResult(
            title=SearchClientBase._text_or_empty(item.get(title_key)),
            snippet=SearchClientBase._text_or_empty(item.get(snippet_key)),
            url=SearchClientBase._text_or_empty(item.get(url_key)),
            source=source,
        )

    @classmethod
    def _build_search_results(
        cls,
        items: list[dict[str, JSONValue]],
        *,
        source: str,
        title_key: str,
        snippet_key: str,
        url_key: str,
        max_results: int,
    ) -> list[SearchResult]:
        return [
            cls._build_search_result(
                item,
                source=source,
                title_key=title_key,
                snippet_key=snippet_key,
                url_key=url_key,
            )
            for item in items[:max_results]
        ]

    async def _log_retry(self, attempt: int, error: Exception) -> None:
        logger = get_logger(LOGGER_NAME)
        delay = compute_exponential_backoff_seconds(
            attempt,
            base_seconds=float(self.retry_delay),
            maximum_seconds=60.0,
            jitter_ratio=0.1,
        )
        logger.warning(
            "%s search attempt %s/%s failed: %s: %s. Retrying in %.2fs",
            self.PROVIDER_NAME,
            attempt + 1,
            self.max_retries,
            type(error).__name__,
            str(error),
            delay,
        )
        await asyncio.sleep(delay)

    def _raise_final_error(self, error: Exception, query: str | None = None) -> NoReturn:
        context = f"provider={self.PROVIDER_NAME}, retries={self.max_retries}"
        if query:
            context += f", query={query[:50]}..."
        raise ValidationError(
            f"{self.PROVIDER_NAME} search failed after {self.max_retries} attempts ({context}): {type(error).__name__}: {error}",
        ) from error

    async def _request(
        self,
        method: str,
        url: str,
        *,
        query: str | None = None,
        timeout: float | httpx2.Timeout | None = None,
        params: QueryParamsInput | None = None,
        headers: HeadersInput | None = None,
        json_payload: JSONValue | None = None,
        follow_redirects: bool | None = None,
    ) -> JSONValue:
        last_error: Exception | None = None
        request_timeout = timeout if timeout is not None else float(self.timeout)
        redirects = (
            bool(follow_redirects) if follow_redirects is not None else httpx2.USE_CLIENT_DEFAULT
        )

        for attempt in range(self.max_retries):
            try:
                response = await self.http_client.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    json=json_payload,
                    follow_redirects=redirects,
                    timeout=request_timeout,
                )
                response.raise_for_status()
                return read_http_json_value(response, field=f"{self.PROVIDER_NAME} response")
            except httpx2.HTTPStatusError as exception:
                status_code = exception.response.status_code
                if status_code >= 500 or status_code == 429:
                    last_error = exception
                    if attempt < self.max_retries - 1:
                        await self._log_retry(attempt, exception)
                else:
                    self._raise_final_error(exception, query=query)
            except (
                httpx2.RequestError,
                OSError,
                ValidationError,
            ) as exception:
                last_error = exception
                if attempt < self.max_retries - 1:
                    await self._log_retry(attempt, exception)
        if last_error is None:
            raise StateError("Loop completed without setting last_error.")
        self._raise_final_error(last_error, query=query)
