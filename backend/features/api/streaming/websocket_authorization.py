"""SoAI - Connection-owned bounded WebSocket authorization reads [backend/features/api/streaming/websocket_authorization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError
from core.logging.protocols import LoggerProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

__all__ = ("WebsocketAuthorization",)

OPERATION_AUTHORIZATION = "api_system.websocket.authorization"
OPERATION_LATE_FAILURE = "api_system.websocket.authorization.late_failure"


class WebsocketAuthorization:

    def __init__(
        self,
        *,
        logger: LoggerProtocol,
        cancellation_binder: TaskCancellationBinderProtocol | None,
        finalizer_tracker: TaskFinalizerTrackerProtocol | None,
        cancellation_id: str,
    ) -> None:
        self.shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._query_task: asyncio.Task[None] | None = None
        self._logger = logger
        self._cancellation_binder = cancellation_binder
        self._finalizer_tracker = finalizer_tracker
        self._cancellation_id = cancellation_id

    def close(self) -> None:
        self.shutdown_event.set()
        if self._query_task is not None and not self._query_task.done():
            self._query_task.cancel()

    async def resolve[Result](
        self,
        operation: Callable[[], Awaitable[Result]],
        *,
        deadline: MonotonicDeadline | None = None,
    ) -> Result:
        deadline = deadline if deadline is not None else deadline_after(LOCAL_IO_TIMEOUT_SEC)
        started_monotonic = time.monotonic()
        phase = "authorization_lock"
        result: list[Result] = []
        waiting = True

        async def query() -> None:
            result.append(await operation())

        def query_completed(task: asyncio.Task[None]) -> None:
            if self._query_task is task:
                self._query_task = None
            if not waiting and not task.cancelled():
                exception = task.exception()
                if exception is not None:
                    log_exception(
                        self._logger,
                        exception,
                        message="Closed WebSocket authorization read failed after cancellation.",
                        operation=OPERATION_LATE_FAILURE,
                    )

        try:
            async with asyncio.timeout(deadline.remaining_seconds()):
                async with self._lock:
                    phase = "authorization_query"
                    if self.shutdown_event.is_set():
                        raise asyncio.CancelledError
                    query_task = spawn_tracked_task(
                        query(),
                        name="ws-authorization-read",
                        logger=self._logger,
                        cancellation_binder=self._cancellation_binder,
                        finalizer_tracker=self._finalizer_tracker,
                        cancellation_id=self._cancellation_id,
                        owner="ws_authorization",
                        owner_observes_result=True,
                        done_callback=query_completed,
                    )
                    self._query_task = query_task
                    completed, _pending = await asyncio.wait(
                        {query_task}, timeout=deadline.remaining_seconds()
                    )
                    if not completed:
                        raise TimeoutError
                    if self.shutdown_event.is_set():
                        raise asyncio.CancelledError
                    query_task.result()
                    return result[0]
        except TimeoutError as exception:
            self.close()
            raise SoAITimeoutError(
                "WebSocket authorization could not be verified before its deadline.",
                operation=OPERATION_AUTHORIZATION,
                details={
                    "phase": phase,
                    "elapsed_ms": max(0, int((time.monotonic() - started_monotonic) * 1000)),
                    "remaining_ms": max(0, int(deadline.remaining_seconds() * 1000)),
                },
            ) from exception
        except asyncio.CancelledError:
            self.close()
            raise
        finally:
            waiting = False
