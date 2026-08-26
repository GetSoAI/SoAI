"""SoAI - Browser download saver task lifecycle [backend/mcp/tools/browser/download_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from mcp.tools.browser.download_files import save_browser_download_file
from mcp.tools.browser.download_task_state import (
    allocate_download_task_target_path,
    record_download_task_status,
)
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)

if TYPE_CHECKING:
    from mcp.tools.browser.types import BrowserSessionState, PendingBrowserDownload

__all__ = (
    "cancel_active_download_tasks",
    "spawn_download_saver_task",
)

LOGGER_NAME = "SoAI.mcp.tools.download_tasks"
OWNER = "mcp.browser_download"
OPERATION_SAVE = "mcp.browser.download.save_task"
DOWNLOAD_SAVE_TASK_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    ValidationError,
    *PLAYWRIGHT_OPERATION_EXCEPTIONS,
)


async def _run_download_saver(
    state: BrowserSessionState,
    pending: PendingBrowserDownload,
    *,
    download_id: str,
    downloads_dir: str,
    suggested_filename: str,
    download_url: str,
) -> None:
    target_path: str | None = None
    try:
        failure = await pending.download.failure()
        if isinstance(failure, str) and failure.strip():
            await record_download_task_status(
                state,
                download_id=download_id,
                status="canceled",
                file_path=None,
                error=failure.strip(),
                target_path=None,
                remove_task=True,
            )
            return
        target_path = await allocate_download_task_target_path(
            state,
            downloads_dir=downloads_dir,
            suggested_filename=suggested_filename,
        )
        await save_browser_download_file(
            storage_manager=state.storage_manager,
            download=pending.download,
            downloads_dir=downloads_dir,
            target_path=target_path,
            download_url=download_url,
            expected_size_bytes=pending.expected_size_bytes,
        )
        await record_download_task_status(
            state,
            download_id=download_id,
            status="completed",
            file_path=target_path,
            error=None,
            target_path=target_path,
            remove_task=True,
        )
    except asyncio.CancelledError:
        await record_download_task_status(
            state,
            download_id=download_id,
            status="canceled",
            file_path=None,
            error="Browser download saving was canceled because the browser session closed.",
            target_path=target_path,
            remove_task=True,
        )
        raise
    except DOWNLOAD_SAVE_TASK_FAILURE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_SAVE,
            details={"download_id": download_id, "url": download_url},
        )
        log_exception(
            logger,
            coerced,
            message="Browser download saver task failed.",
            operation=OPERATION_SAVE,
            details={"download_id": download_id, "url": download_url},
            level="warning",
        )
        await record_download_task_status(
            state,
            download_id=download_id,
            status="failed",
            file_path=None,
            error=coerced.message,
            target_path=target_path,
            remove_task=True,
        )


def spawn_download_saver_task(
    state: BrowserSessionState,
    pending: PendingBrowserDownload,
    *,
    download_id: str,
    downloads_dir: str,
    suggested_filename: str,
    download_url: str,
) -> asyncio.Task[None]:
    if state.cancellation_binder is None:
        raise ValidationError("Browser download task cancellation binder is required.")
    if state.finalizer_tracker is None:
        raise ValidationError("Browser download task finalizer tracker is required.")
    cancellation_id = build_soai_id(
        (
            "sys",
            "mcp",
            "browser_download",
            safe_or_hashed_segment(state.owner_key),
            safe_or_hashed_segment(download_id),
        ),
    )
    return spawn_tracked_task(
        _run_download_saver(
            state,
            pending,
            download_id=download_id,
            downloads_dir=downloads_dir,
            suggested_filename=suggested_filename,
            download_url=download_url,
        ),
        name=f"browser-download-{download_id}",
        logger=get_logger(LOGGER_NAME),
        cancellation_binder=state.cancellation_binder,
        cancellation_id=cancellation_id,
        owner=OWNER,
        metadata={"owner_key": state.owner_key, "download_id": download_id},
        finalizer_tracker=state.finalizer_tracker,
    )


async def cancel_active_download_tasks(
    state: BrowserSessionState,
    *,
    reason: str,
) -> None:
    async with state.lock:
        tasks = list(state.download_tasks.values())
    if not tasks:
        return
    logger = get_logger(LOGGER_NAME)
    await cancel_and_await(
        tasks,
        logger=logger,
        task_label="browser download saver task(s)",
        message=f"Cancelling browser download saver task(s) during {reason}.",
        timeout_sec=None,
    )
    async with state.lock:
        for download_id, task in list(state.download_tasks.items()):
            if task.done():
                state.download_tasks.pop(download_id, None)
