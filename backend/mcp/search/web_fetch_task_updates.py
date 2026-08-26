"""SoAI - MCP web fetch task status updates and finalization [backend/mcp/search/web_fetch_task_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.progress.formatting import format_transfer_details
from core.tasks.enums import TaskStatus
from core.tasks.protocols_registry import TaskRegistryProtocol
from core.tasks.status_transitions import update_progress, update_status
from core.tasks.task_cancellation import cancel
from mcp.search.task_lifecycle import complete_task
from mcp.search.web_fetch_progress import WebFetchTaskProgressReporter

if TYPE_CHECKING:
    from core.tasks.protocols import CancellationHistoryProtocol
    from core.tasks.task import Task
    from mcp.rag.scraper.types import FetchedContent

__all__ = (
    "ensure_web_fetch_task_has_progress_total",
    "finalize_web_fetch_task_success_noncritical",
    "mark_web_fetch_task_cancelled_noncritical",
    "try_load_task_for_web_fetch",
)

OPERATION_MCP_SEARCH_FETCH_URL = "mcp.search.fetch_url"
OPERATION_MCP_SEARCH_FETCH_URL_CANCEL = "mcp.search.fetch_url.cancel"
OPERATION_MCP_SEARCH_FETCH_URL_UPDATE_PROGRESS = "mcp.search.fetch_url.update_progress"
OPERATION_MCP_SEARCH_FETCH_URL_UPDATE_STATUS = "mcp.search.fetch_url.update_status"


async def try_load_task_for_web_fetch(
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    logger: LoggerProtocol,
) -> Task | None:
    try:
        return await task_registry.get(task_id)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to load task for web fetch progress tracking (non-critical).",
            operation=OPERATION_MCP_SEARCH_FETCH_URL,
            details={"task_id": task_id},
            level="debug",
        )
        return None


async def ensure_web_fetch_task_has_progress_total(
    *,
    task_registry: TaskRegistryProtocol,
    task: Task,
    logger: LoggerProtocol,
) -> None:
    if task.progress_total is not None:
        return
    try:
        await update_status(
            task_registry,
            task.task_id,
            TaskStatus.WORKING,
            progress_total=100,
            progress_current=0 if task.progress_current is None else task.progress_current,
        )
    except RECOVERABLE_EXCEPTIONS as status_err:
        log_handled_exception(
            logger,
            status_err,
            message="Task status update failed for web fetch (non-critical).",
            operation=OPERATION_MCP_SEARCH_FETCH_URL_UPDATE_STATUS,
            details={"task_id": task.task_id},
            level="debug",
        )


async def finalize_web_fetch_task_success_noncritical(
    *,
    task_registry: TaskRegistryProtocol,
    task: Task,
    fetch_label: str,
    reporter: WebFetchTaskProgressReporter,
    result: FetchedContent,
    logger: LoggerProtocol,
) -> None:
    try:
        final_details = format_transfer_details(
            reporter.last_reported_bytes,
            None,
            speed=reporter.speed,
            eta_seconds=0.0,
        )
        await update_progress(
            task_registry,
            task.task_id,
            progress_current=100,
            status_message=f"Completed download {fetch_label}",
            details=final_details,
        )
    except RECOVERABLE_EXCEPTIONS as progress_err:
        log_handled_exception(
            logger,
            progress_err,
            message="Task progress update failed for web fetch (non-critical).",
            operation=OPERATION_MCP_SEARCH_FETCH_URL_UPDATE_PROGRESS,
            details={"task_id": task.task_id},
            level="debug",
        )
    await complete_task(
        task_registry,
        task.task_id,
        result={"content_type": result.content_type, "title": result.title},
    )


async def mark_web_fetch_task_cancelled_noncritical(
    *,
    task_registry: TaskRegistryProtocol,
    task: Task,
    cancellation_history: CancellationHistoryProtocol,
    logger: LoggerProtocol,
) -> None:
    try:
        cancel_id = task.cancellation_id
        reason = await cancellation_history.get_reason(cancel_id) if cancel_id else None
        await cancel(
            task_registry,
            task.task_id,
            reason=reason or "Request cancelled by user",
        )
    except RECOVERABLE_EXCEPTIONS as cancel_err:
        log_handled_exception(
            logger,
            cancel_err,
            message="Task cancellation update failed for web fetch (non-critical).",
            operation=OPERATION_MCP_SEARCH_FETCH_URL_CANCEL,
            details={"task_id": task.task_id},
            level="debug",
        )
