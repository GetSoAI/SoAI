"""SoAI - MCP web search execution engine [backend/mcp/search/web_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_search import (
    MCP_SEARCH_COUNTER_SEARCHES_BY_PROVIDER,
    MCP_SEARCH_COUNTER_SEARCHES_FAILED,
    MCP_SEARCH_COUNTER_SEARCHES_SUCCEEDED,
    MCP_SEARCH_COUNTER_SEARCHES_TOTAL,
    MCP_SEARCH_TIMING_SEARCH_LATENCY_MS,
)
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.tasks.task_cancellation import cancel
from core.tasks.type_catalog import TASK_TYPE_WEB_SEARCH
from core.timing.monotonic import monotonic_ms
from core.users.ocr_preferences import resolve_user_ocr_language
from mcp.rag.scraper.types import FetchedContent
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.dependencies import MCPSearchDependencies
from mcp.search.models import SearchResult
from mcp.search.providers import (
    list_supported_providers,
    normalize_search_provider_name,
    resolve_search_provider_class,
)
from mcp.search.task_lifecycle import (
    await_with_task_cancellation,
    complete_task,
    fail_task,
)
from mcp.search.web_fetching import fetch_url

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("MCPWebSearch",)

LOGGER_NAME = "SoAI.mcp.search.web_search"
OPERATION = "mcp.search.service.cancel_task_cleanup"


class MCPWebSearch:
    def __init__(
        self,
        deps: MCPSearchDependencies,
        *,
        api_key_resolver: Callable[[str], Awaitable[str | None]],
    ) -> None:
        self.database_users = deps.database_users
        self.config = deps.config
        self.http_client = deps.http_client
        self.web_fetcher = deps.web_fetcher
        self.runtime_flags = deps.runtime_flags
        self.metrics = deps.metrics_manager
        self.task_registry = deps.task_registry
        self.event_bus = deps.event_bus
        self._cancellation_history = deps.cancellation_history
        self._cancellation_event_bus = deps.cancellation_event_bus
        self._token_collection = deps.token_collection
        self._search_providers = deps.search_providers
        self._api_key_resolver = api_key_resolver
        self.default_provider = self.config.require_str("TOOLS.RAG.WEB.DEFAULT_PROVIDER")
        self._clients: dict[str, SearchClientBase] = {}

    def list_supported_providers(self) -> list[str]:
        return list_supported_providers(self._search_providers)

    def _resolve_provider_class(self, provider: str) -> type[SearchClientBase] | None:
        return resolve_search_provider_class(provider, self._search_providers)

    def _get_client(self, provider: str) -> SearchClientBase:
        if provider not in self._clients:
            provider_cls = self._resolve_provider_class(provider)
            if provider_cls is None:
                available = ", ".join(self.list_supported_providers())
                raise ValidationError(
                    f"Unknown search provider: {provider}. Available: {available}",
                )
            self._clients[provider] = provider_cls(
                self.config,
                self.runtime_flags,
                self.http_client,
                api_key_resolver=self._api_key_resolver,
            )
        return self._clients[provider]

    def _to_dicts(self, results: list[SearchResult]) -> list[JSONDict]:
        return [
            {
                "title": result.title,
                "snippet": result.snippet,
                "url": result.url,
                "source": result.source,
            }
            for result in results
        ]

    async def fetch_url(
        self,
        url: str,
        *,
        user_id: int = 0,
        owner_id: str | None = None,
        task_id: str | None = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> FetchedContent:
        return await fetch_url(
            url,
            ocr_language=await resolve_user_ocr_language(self.database_users, user_id),
            web_fetcher=self.web_fetcher,
            task_registry=self.task_registry,
            cancellation_history=self._cancellation_history,
            cancellation_event_bus=self._cancellation_event_bus,
            token_collection=self._token_collection,
            metrics=self.metrics,
            user_id=user_id,
            owner_id=owner_id,
            task_id=task_id,
            progress_start=progress_start,
            progress_end=progress_end,
        )

    async def _execute_search(
        self,
        provider: str,
        search_coro: Awaitable[list[SearchResult]],
        *,
        query: str = "",
        user_id: int = 0,
        owner_id: str | None = None,
        owner_type: str = "conversation",
    ) -> list[JSONDict]:
        logger = get_logger(LOGGER_NAME)
        if self.metrics is not None:
            self.metrics.increment_counter(*MCP_SEARCH_COUNTER_SEARCHES_TOTAL)
            self.metrics.increment_counter(*MCP_SEARCH_COUNTER_SEARCHES_BY_PROVIDER, provider)
        start_time_ms = monotonic_ms()
        task: Task | None = None
        if self.task_registry is not None and owner_id:
            task = await create(
                self.task_registry,
                task_type=TASK_TYPE_WEB_SEARCH,
                user_id=user_id,
                owner_id=owner_id,
                owner_type=owner_type,
                cancellation_id=build_soai_id(
                    (
                        "task",
                        "mcp",
                        "web_search",
                        owner_type,
                        owner_id,
                        uuid.uuid4().hex[:12],
                    ),
                ),
                status=TaskStatus.WORKING,
                progress_total=100,
                metadata={"provider": provider, "query": query},
            )
        try:
            results: list[SearchResult]
            if task:
                results = await await_with_task_cancellation(
                    self._token_collection,
                    self._cancellation_history,
                    self._cancellation_event_bus,
                    task,
                    search_coro,
                    f"search:{provider}",
                )
            else:
                results = await search_coro
            if self.metrics is not None:
                self.metrics.increment_counter(*MCP_SEARCH_COUNTER_SEARCHES_SUCCEEDED)
            result_dicts = self._to_dicts(results)
            if task is not None:
                await complete_task(
                    self.task_registry,
                    task.task_id,
                    result={"count": len(result_dicts)},
                )
            return result_dicts
        except asyncio.CancelledError:
            if task is not None and self.task_registry is not None:
                try:
                    cancel_id = task.cancellation_id
                    reason = (
                        await self._cancellation_history.get_reason(cancel_id)
                        if cancel_id
                        else None
                    )
                    await cancel(
                        self.task_registry,
                        task.task_id,
                        reason=reason or "Request cancelled by user",
                    )
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Task cancellation cleanup failed (non-critical).",
                        operation=OPERATION,
                        details={"task_id": task.task_id},
                        level="debug",
                    )
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            if self.metrics is not None:
                self.metrics.increment_counter(*MCP_SEARCH_COUNTER_SEARCHES_FAILED)
            if task is not None:
                await fail_task(self.task_registry, task.task_id, str(exception))
            raise
        finally:
            if self.metrics is not None:
                self.metrics.record_timing(
                    *MCP_SEARCH_TIMING_SEARCH_LATENCY_MS,
                    duration_ms=float(monotonic_ms() - start_time_ms),
                )

    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        provider: str | None = None,
        user_id: int = 0,
        owner_id: str | None = None,
        owner_type: str = "conversation",
        **search_options: JSONValue,
    ) -> list[JSONDict]:
        effective_provider = normalize_search_provider_name(
            provider or self.default_provider,
            self._search_providers,
        )
        client = self._get_client(effective_provider)
        return await self._execute_search(
            effective_provider,
            client.search(query, max_results, **search_options),
            query=query,
            user_id=user_id,
            owner_id=owner_id,
            owner_type=owner_type,
        )
