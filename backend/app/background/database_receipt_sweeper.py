"""SoAI - Periodic database operation receipt retention [backend/app/background/database_receipt_sweeper.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import (
    await_background_task_shutdown,
    run_background_periodic_task,
)
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC
from core.timing.epoch import epoch_ms
from database.operation_receipts import (
    DATABASE_RECEIPT_CLEANUP_BATCH_SIZE,
    sync_delete_expired_database_write_receipts,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("DatabaseReceiptSweeper", "DatabaseReceiptSweeperDependencies")

LOGGER_NAME = "SoAI.app.background.database_receipt_sweeper"


@dataclass(frozen=True, slots=True)
class DatabaseReceiptSweeperDependencies:
    database_core: DatabaseCoreProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DatabaseReceiptSweeperDependencies",
            cancellation_binder=self.cancellation_binder,
            database_core=self.database_core,
            finalizer_tracker=self.finalizer_tracker,
        )


class DatabaseReceiptSweeper:
    def __init__(self, deps: DatabaseReceiptSweeperDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._shutdown_event = asyncio.Event()
        self._task = run_background_periodic_task(
            shutdown_event=self._shutdown_event,
            interval_seconds=float(LONG_IDLE_TIMEOUT_SEC),
            task=self._run_once,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="database",
                owner="receipt_sweeper",
                include_random_suffix=False,
            ),
            owner="database_receipts",
            name="database-receipt-sweeper",
            logger=self._logger,
            metadata={
                "interval_ms": LONG_IDLE_TIMEOUT_SEC * 1000,
                "batch_limit": DATABASE_RECEIPT_CLEANUP_BATCH_SIZE,
            },
            task_name="database_receipt_cleanup",
            run_immediately=True,
        )

    async def _run_once(self) -> None:
        now_ms = epoch_ms()
        deleted_total = 0
        while not self._shutdown_event.is_set():
            deleted = await self._deps.database_core.writer.queue_write_operation(
                sync_delete_expired_database_write_receipts,
                now_ms,
            )
            deleted_total += deleted
            if deleted < DATABASE_RECEIPT_CLEANUP_BATCH_SIZE:
                break
        if deleted_total:
            self._logger.info("Deleted %d expired database operation receipts.", deleted_total)

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        task, self._task = self._task, None
        await await_background_task_shutdown(
            task,
            logger=self._logger,
            operation="app.background.database_receipt_sweeper.shutdown",
            message="Database receipt sweeper failed during shutdown (non-critical).",
            level="debug",
        )
