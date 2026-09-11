"""SoAI - Enqueue DB write operations for DatabaseIOController [backend/database/io/controller/operation_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Callable
from queue import Full, Queue

from core.logging.trace import get_logger
from core.mutations.identifiers import create_timestamped_operation_id
from core.state.errors import (
    DatabaseQueueSaturatedError,
    DatabaseTimeoutError,
    DatabaseUnavailableError,
)
from database.io.controller.write_job import DatabaseWriteJob
from database.io.internal_protocols import (
    DatabaseWriteJobProtocol,
    OperationStatus,
    ShutdownSentinel,
)
from database.io.operation_status_tracker import OperationStatusTracker

__all__ = ("DatabaseWriteOperationQueue",)

LOGGER_NAME = "SoAI.database.io.operation_queue"


class DatabaseWriteOperationQueue:
    def __init__(
        self,
        *,
        queue: Queue[DatabaseWriteJobProtocol | type[ShutdownSentinel]],
        status_tracker: OperationStatusTracker,
        is_running: Callable[[], bool],
        default_operation_timeout: float,
    ) -> None:
        self._queue = queue
        self._status_tracker = status_tracker
        self._is_running = is_running
        self._default_operation_timeout = default_operation_timeout

    def get_operation_status(self, operation_id: str) -> OperationStatus | None:
        if not isinstance(operation_id, str) or not operation_id:
            return None
        self._status_tracker.prune()
        return self._status_tracker.get_status(operation_id)

    def has_pending_write_operations(self) -> bool:
        return not self._queue.empty()

    async def queue_write_operation[*Ts, T](
        self,
        func: Callable[[sqlite3.Connection, *Ts], T],
        *args: *Ts,
        enqueue_timeout: float | None = None,
        operation_timeout: float | None = None,
    ) -> T:
        logger = get_logger(LOGGER_NAME)
        if not self._is_running():
            raise DatabaseUnavailableError("Database writer thread is not running.")
        try:
            operation_name = func.__name__
        except AttributeError:
            operation_name = "unknown"
        operation_id = create_timestamped_operation_id("dbop")
        future: asyncio.Future[T] | None = asyncio.get_running_loop().create_future()
        if future is None:
            raise DatabaseUnavailableError("Future was not created.")
        cancelled = threading.Event()
        try:
            self._status_tracker.record(operation_id, OperationStatus.PENDING)
            try:
                await self._enqueue_job(
                    DatabaseWriteJob(
                        func=func,
                        args=args,
                        future=future,
                        cancelled=cancelled,
                        operation_id=operation_id,
                        operation_name=operation_name,
                    ),
                    enqueue_timeout=enqueue_timeout,
                )
            except asyncio.CancelledError:
                self._mark_cancelled_by_caller(operation_id, cancelled=cancelled, future=future)
                logger.debug(
                    "Cancelled while enqueuing database operation: %s (op_id=%s)",
                    operation_name,
                    operation_id,
                )
                raise

            try:
                timeout_value = (
                    operation_timeout
                    if operation_timeout is not None
                    else self._default_operation_timeout
                )
                result = await asyncio.wait_for(future, timeout=timeout_value)
                self._status_tracker.mark_acknowledged(operation_id)
                return result
            except asyncio.CancelledError:
                self._mark_cancelled_by_caller(operation_id, cancelled=cancelled, future=future)
                status = self._status_tracker.get_status(operation_id)
                logger.debug(
                    "Cancelled while waiting for database operation result: %s (op_id=%s, status=%s)",
                    operation_name,
                    operation_id,
                    status,
                )
                raise
            except TimeoutError as exception:
                cancelled.set()
                future.cancel()
                status = self._status_tracker.get_status(operation_id)
                if status is OperationStatus.COMMITTED:
                    raise DatabaseTimeoutError(
                        "Database operation timed out after commit.",
                        details={
                            "operation_id": operation_id,
                            "status_url": self._status_url(operation_id),
                            "retry_guidance": "do_not_retry",
                            "status": status.value,
                        },
                        headers={"X-SoAI-Operation-Id": operation_id},
                    ) from exception
                if status is OperationStatus.OUTCOME_UNKNOWN:
                    raise DatabaseTimeoutError(
                        "Database operation timed out with an unknown commit outcome.",
                        details={
                            "operation_id": operation_id,
                            "status_url": self._status_url(operation_id),
                            "retry_guidance": "do_not_retry",
                            "status": status.value,
                        },
                        headers={"X-SoAI-Operation-Id": operation_id},
                    ) from exception
                if status == OperationStatus.FAILED:
                    raise DatabaseTimeoutError(
                        "Database operation timed out after failure.",
                        details={
                            "operation_id": operation_id,
                            "status_url": self._status_url(operation_id),
                            "retry_guidance": "check_status_before_retry",
                            "status": status.value,
                        },
                        headers={"X-SoAI-Operation-Id": operation_id},
                    ) from exception
                if not self._is_running():
                    if status is OperationStatus.PENDING:
                        self._status_tracker.record_if_not_terminal(
                            operation_id,
                            OperationStatus.SKIPPED,
                            error_type="WriterSessionReset",
                        )
                        status = OperationStatus.SKIPPED
                    raise DatabaseTimeoutError(
                        "Database operation timed out while the writer became unavailable.",
                        details={
                            "operation_id": operation_id,
                            "status_url": self._status_url(operation_id),
                            "retry_guidance": "check_status_before_retry",
                            "status": status.value if status is not None else "pending",
                        },
                        headers={"X-SoAI-Operation-Id": operation_id},
                    ) from exception
                raise DatabaseTimeoutError(
                    "Database operation timed out with an unresolved outcome.",
                    details={
                        "operation_id": operation_id,
                        "status_url": self._status_url(operation_id),
                        "retry_guidance": "check_status_before_retry",
                        "status": status.value if status is not None else "pending",
                    },
                    headers={"X-SoAI-Operation-Id": operation_id},
                ) from exception
        except Full as exception:
            if not future.done():
                future.cancel()
            self._status_tracker.record(
                operation_id,
                OperationStatus.FAILED,
                error_type="QueueSaturated",
            )
            raise DatabaseQueueSaturatedError(
                "Database write queue is at capacity. Try again later.",
            ) from exception

    def _mark_cancelled_by_caller[T](
        self,
        operation_id: str,
        *,
        cancelled: threading.Event,
        future: asyncio.Future[T] | None = None,
    ) -> None:
        cancelled.set()
        if future is not None and not future.done():
            future.cancel()
        status = self._status_tracker.get_status(operation_id)
        if status is OperationStatus.PENDING:
            self._status_tracker.record(
                operation_id,
                OperationStatus.SKIPPED,
                error_type="CancelledByCaller",
            )

    async def _enqueue_job(
        self,
        job: DatabaseWriteJobProtocol,
        *,
        enqueue_timeout: float | None,
    ) -> None:
        if enqueue_timeout is None:
            self._queue.put_nowait(job)
            return
        await asyncio.to_thread(self._queue.put, job, True, enqueue_timeout)

    @staticmethod
    def _status_url(operation_id: str) -> str:
        return f"/api/v1/system/database/operations/{operation_id}"
