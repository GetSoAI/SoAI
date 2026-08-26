"""SoAI - Core cancellation primitives [backend/core/concurrency/cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, override

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.constants import MODERATE_DELAY_SEC

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONValue

__all__ = (
    "CancellationToken",
    "TaskCancelledError",
    "create_cancellation_watch_task",
    "make_task_cancel_callback",
)

LOGGER_NAME = "SoAI.core.concurrency.cancellation"
OPERATION = "core.concurrency.cancellation.cancel"


class TaskCancelledError(StateError):
    def __init__(self, cancellation_id: str, reason: str | None = None) -> None:
        self.cancellation_id = cancellation_id
        self.reason = reason or "Task cancelled."
        super().__init__(
            message=self.reason,
            details={"cancellation_id": cancellation_id},
        )

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.cancellation_id,), {"reason": self.reason})


class CancellationToken:
    __slots__ = (
        "_async_event",
        "_cancel_lock",
        "_loop",
        "_on_cancel",
        "cancellation_id",
        "cancellation_reason",
        "metadata",
        "owner",
        "thread_event",
    )

    def __init__(
        self,
        cancellation_id: str,
        *,
        owner: str = "",
        metadata: dict[str, JSONValue] | None = None,
        on_cancel: Callable[[str], None] | None = None,
    ) -> None:
        if not cancellation_id:
            raise ValidationError("cancellation_id is required.")
        self.cancellation_id = cancellation_id
        self.owner = owner
        self.metadata: dict[str, JSONValue] = dict(metadata or {})
        self._async_event = asyncio.Event()
        self.thread_event = threading.Event()
        self.cancellation_reason: str | None = None
        self._on_cancel = on_cancel
        self._cancel_lock = threading.Lock()
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    @override
    def __repr__(self) -> str:
        return (
            "CancellationToken("
            f"cancellation_id={self.cancellation_id!r}, owner={self.owner!r}"
            ")"
        )

    async def wait(self) -> None:
        while not self.thread_event.is_set():
            try:
                await asyncio.wait_for(
                    self._async_event.wait(),
                    timeout=MODERATE_DELAY_SEC,
                )
                return
            except TimeoutError:
                continue

    def is_cancelled(self) -> bool:
        if self.thread_event.is_set():
            return True
        return self._async_event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.thread_event.is_set():
            raise TaskCancelledError(self.cancellation_id, self.cancellation_reason)

    def cancel(self, reason: str) -> bool:
        logger = get_logger(LOGGER_NAME)
        with self._cancel_lock:
            if self.thread_event.is_set():
                return False
            self.cancellation_reason = reason
            self.thread_event.set()
            loop = self._loop
            if loop is None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
            if loop is not None and (not loop.is_closed()):
                try:
                    loop.call_soon_threadsafe(self._async_event.set)
                except RuntimeError:
                    logger.debug(
                        "Could not signal async event for %s: loop not accepting callbacks",
                        self.cancellation_id,
                    )
            else:
                logger.debug(
                    "Could not signal async event for %s: no running loop available",
                    self.cancellation_id,
                )
        if self._on_cancel:
            try:
                self._on_cancel(reason)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Cancellation callback failed.",
                    operation=OPERATION,
                    details={"cancellation_id": self.cancellation_id},
                )
        return True


def make_task_cancel_callback[TaskResult](
    loop: asyncio.AbstractEventLoop,
    task: asyncio.Task[TaskResult],
    cancellation_id: str,
    owner: str = "",
) -> Callable[[str], None]:
    if not cancellation_id:
        raise ValidationError("cancellation_id is required.")

    def _cancel_task(reason: str) -> None:
        logger = get_logger(LOGGER_NAME)
        if loop.is_closed():
            return
        logger.debug(
            "Cancelling task for cancellation %s (%s) scheduled: %s",
            cancellation_id,
            owner or "unnamed",
            reason,
        )

        def _attempt_cancel() -> None:
            logger = get_logger(LOGGER_NAME)
            if loop.is_closed():
                return
            if task.done():
                logger.debug(
                    "Cancelling task for cancellation %s (%s) ignored because the task already completed.",
                    cancellation_id,
                    owner or "unnamed",
                )
                return
            if task.cancelling() > 0:
                logger.debug(
                    "Cancelling task for cancellation %s (%s) ignored because cancellation is already pending.",
                    cancellation_id,
                    owner or "unnamed",
                )
                return
            logger.debug(
                "Cancelling task for cancellation %s (%s): %s",
                cancellation_id,
                owner or "unnamed",
                reason,
            )
            task.cancel()

        if loop.is_running():
            loop.call_soon_threadsafe(_attempt_cancel)
        else:
            _attempt_cancel()

    return _cancel_task


def create_cancellation_watch_task(
    cancellation_token: CancellationTokenProtocol,
    shutdown_event: asyncio.Event,
    *,
    name: str | None = None,
) -> asyncio.Task[None] | None:
    if cancellation_token.thread_event.is_set():
        shutdown_event.set()
        return None

    async def _watch_cancel() -> None:
        await cancellation_token.wait()
        shutdown_event.set()

    return create_ephemeral_task(
        _watch_cancel(),
        name=name or f"cancellation-watch-{cancellation_token.cancellation_id}",
    )
