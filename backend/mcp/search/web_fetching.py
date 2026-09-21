"""SoAI - MCP web content fetching with cancellation support [backend/mcp/search/web_fetching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_search import (
    MCP_SEARCH_COUNTER_FETCHES_FAILED,
    MCP_SEARCH_COUNTER_FETCHES_SUCCEEDED,
    MCP_SEARCH_COUNTER_FETCHES_TOTAL,
    MCP_SEARCH_TIMING_FETCH_LATENCY_MS,
)
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.tasks.type_catalog import TASK_TYPE_WEB_FETCH
from core.timing.monotonic import monotonic_ms
from mcp.rag.scraper import fetching
from mcp.rag.scraper.types import FetchedContent
from mcp.search.task_lifecycle import await_with_task_cancellation, fail_task
from mcp.search.web_fetch_progress import WebFetchTaskProgressReporter
from mcp.search.web_fetch_task_updates import (
    ensure_web_fetch_task_has_progress_total,
    finalize_web_fetch_task_success_noncritical,
    mark_web_fetch_task_cancelled_noncritical,
    try_load_task_for_web_fetch,
)

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol

__all__ = ("fetch_url",)

LOGGER_NAME = "SoAI.mcp.search.web_fetching"


async def fetch_url(
    url: str,
    *,
    ocr_language: str,
    web_fetcher: WebContentFetcherProtocol,
    task_registry: TaskRegistryProtocol | None,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    token_collection: TokenCollectionProtocol,
    metrics: MetricsManagerProtocol | None,
    user_id: int = 0,
    owner_id: str | None = None,
    task_id: str | None = None,
    progress_start: int = 0,
    progress_end: int = 100,
) -> FetchedContent:
    logger = get_logger(LOGGER_NAME)
    if metrics:
        metrics.increment_counter(*MCP_SEARCH_COUNTER_FETCHES_TOTAL)
    start_time_ms = monotonic_ms()
    task = None
    created_task = False
    if task_registry and task_id:
        task = await try_load_task_for_web_fetch(
            task_registry=task_registry,
            task_id=task_id,
            logger=logger,
        )
    if task_registry and task is None and owner_id:
        task = await create(
            task_registry,
            task_type=TASK_TYPE_WEB_FETCH,
            user_id=user_id,
            owner_id=owner_id,
            owner_type="conversation",
            cancellation_id=build_soai_id(
                ("task", "mcp", "web_fetch", "conversation", owner_id, uuid.uuid4().hex[:12]),
            ),
            status=TaskStatus.WORKING,
            progress_total=100,
            metadata={"url": url},
        )
        created_task = True
    try:
        fetch_label = url if len(url) <= 120 else f"{url[:117]}..."
        reporter = (
            WebFetchTaskProgressReporter(
                task_registry=task_registry,
                task_id=task.task_id,
                progress_start=progress_start,
                progress_end=progress_end,
                fetch_label=fetch_label,
                max_size_bytes=int(web_fetcher.max_size_bytes),
            )
            if task and task_registry
            else None
        )
        if task and task_registry:
            await ensure_web_fetch_task_has_progress_total(
                task_registry=task_registry,
                task=task,
                logger=logger,
            )
        fetch_coro = fetching.fetch_url(
            web_fetcher, url, ocr_language=ocr_language, progress_callback=reporter
        )
        result = (
            await fetch_coro
            if task is None
            else await await_with_task_cancellation(
                token_collection,
                cancellation_history,
                cancellation_event_bus,
                task,
                fetch_coro,
                "fetch_url",
            )
        )
        if metrics:
            metrics.increment_counter(*MCP_SEARCH_COUNTER_FETCHES_SUCCEEDED)
        if task and created_task and task_registry and reporter is not None:
            await finalize_web_fetch_task_success_noncritical(
                task_registry=task_registry,
                task=task,
                fetch_label=fetch_label,
                reporter=reporter,
                result=result,
                logger=logger,
            )
        return result
    except asyncio.CancelledError:
        if task and task_registry:
            await mark_web_fetch_task_cancelled_noncritical(
                task_registry=task_registry,
                task=task,
                cancellation_history=cancellation_history,
                logger=logger,
            )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        if metrics:
            metrics.increment_counter(*MCP_SEARCH_COUNTER_FETCHES_FAILED)
        if task and created_task and task_registry:
            await fail_task(task_registry, task.task_id, str(exception))
        raise
    finally:
        if metrics:
            metrics.record_timing(
                *MCP_SEARCH_TIMING_FETCH_LATENCY_MS,
                duration_ms=float(monotonic_ms() - start_time_ms),
            )
