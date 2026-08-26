"""SoAI - Async queue consumer and action handler processor [backend/core/tasks/action_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.timing.constants import YIELD_CONTROL_SEC

if TYPE_CHECKING:
    type ActionQueueItem[Payload] = tuple[str, Payload]
    type ActionHandler[Payload] = Callable[[str, Payload], Awaitable[None]]

__all__ = (
    "ActionQueueProcessor",
    "consume_async_queue",
    "run_action_queue_processor",
    "run_action_queue_processor_until_sentinel",
)

OPERATION_CORE_TASKS_ACTION_QUEUE_CONSUME_ASYNC_QUEUE = (
    "core.tasks.action_queue.consume_async_queue"
)


OPERATION_TASK_HELPER_ACTION_QUEUE_PROCESSOR = "task_helper.action_queue_processor"
OPERATION_TASK_HELPER_RUN_ACTION_QUEUE_PROCESSOR_UNTIL_SENTINEL = (
    "task_helper.run_action_queue_processor_until_sentinel"
)


async def consume_async_queue[QueueItemT](
    queue: asyncio.Queue[QueueItemT],
    *,
    shutdown_event: asyncio.Event,
    process_item: Callable[[QueueItemT], Awaitable[None]],
    sentinel: QueueItemT | None = None,
    timeout: float | None = None,
    on_timeout: Callable[[], Awaitable[None] | None] | None = None,
    logger: LoggerProtocol | None = None,
    acknowledge: bool = True,
) -> None:
    while not shutdown_event.is_set():
        try:
            get_coro = queue.get()
            item = (
                await asyncio.wait_for(get_coro, timeout=timeout)
                if timeout is not None
                else await get_coro
            )
        except TimeoutError:
            if on_timeout:
                try:
                    timeout_result = on_timeout()
                    if inspect.isawaitable(timeout_result):
                        await timeout_result
                except RECOVERABLE_EXCEPTIONS as exception:
                    if logger:
                        log_exception(
                            logger,
                            exception,
                            message="Queue timeout handler failed",
                            operation=OPERATION_CORE_TASKS_ACTION_QUEUE_CONSUME_ASYNC_QUEUE,
                        )
            continue
        except RECOVERABLE_EXCEPTIONS as exception:
            if logger:
                log_exception(
                    logger,
                    exception,
                    message="Queue consumer failed to retrieve item",
                    operation=OPERATION_CORE_TASKS_ACTION_QUEUE_CONSUME_ASYNC_QUEUE,
                )
            await asyncio.sleep(YIELD_CONTROL_SEC)
            continue
        is_sentinel = False
        try:
            is_sentinel = item is sentinel
            if not is_sentinel:
                await process_item(item)
        except RECOVERABLE_EXCEPTIONS as exception:
            if logger:
                log_exception(
                    logger,
                    exception,
                    message="Queue consumer failed while processing item",
                    operation=OPERATION_CORE_TASKS_ACTION_QUEUE_CONSUME_ASYNC_QUEUE,
                )
        finally:
            if acknowledge:
                try:
                    queue.task_done()
                except ValueError:
                    if logger:
                        logger.debug("Queue task_done() called after queue closure.")
        if is_sentinel:
            break


class ActionQueueProcessor[PayloadT]:

    def __init__(
        self,
        *,
        handlers: dict[str, Callable[[str, PayloadT], Awaitable[None]]],
        logger: LoggerProtocol,
        shutdown_event: asyncio.Event,
        timeout: float | None = None,
        on_unknown_action: Callable[[str, PayloadT], None] | None = None,
    ) -> None:
        self._handlers = handlers
        self._logger = logger
        self._shutdown_event = shutdown_event
        self._timeout = timeout
        self._on_unknown_action = on_unknown_action

    async def run(self, queue: asyncio.Queue[tuple[str, PayloadT] | None]) -> None:

        async def _process(task: tuple[str, PayloadT] | None) -> None:
            if task is None:
                return
            action, payload = task
            handler = self._handlers.get(action)
            if handler is None:
                if self._on_unknown_action:
                    self._on_unknown_action(action, payload)
                else:
                    self._logger.warning("Unknown queue action: %s", action)
                return
            try:
                await handler(action, payload)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message=f"Queue handler for '{action}' failed",
                    operation=OPERATION_TASK_HELPER_ACTION_QUEUE_PROCESSOR,
                )

        await consume_async_queue(
            queue,
            shutdown_event=self._shutdown_event,
            process_item=_process,
            logger=self._logger,
            timeout=self._timeout,
        )


async def run_action_queue_processor[PayloadT](
    queue: asyncio.Queue[ActionQueueItem[PayloadT] | None],
    *,
    handlers: dict[str, ActionHandler[PayloadT]],
    logger: LoggerProtocol,
    shutdown_event: asyncio.Event,
    timeout: float | None = None,
    on_unknown_action: Callable[[str, PayloadT], None] | None = None,
) -> None:
    processor = ActionQueueProcessor[PayloadT](
        handlers=handlers,
        logger=logger,
        shutdown_event=shutdown_event,
        timeout=timeout,
        on_unknown_action=on_unknown_action,
    )
    await processor.run(queue)


async def run_action_queue_processor_until_sentinel[PayloadT](
    queue: asyncio.Queue[ActionQueueItem[PayloadT] | None],
    *,
    handlers: dict[str, ActionHandler[PayloadT]],
    logger: LoggerProtocol,
    timeout: float | None = None,
    on_unknown_action: Callable[[str, PayloadT], None] | None = None,
) -> None:

    async def _process(task: ActionQueueItem[PayloadT] | None) -> None:
        if task is None:
            return
        action, payload = task
        handler = handlers.get(action)
        if handler is None:
            if on_unknown_action:
                on_unknown_action(action, payload)
            else:
                logger.warning("Unknown queue action: %s", action)
            return
        try:
            await handler(action, payload)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Queue handler for '{action}' failed",
                operation=OPERATION_TASK_HELPER_RUN_ACTION_QUEUE_PROCESSOR_UNTIL_SENTINEL,
            )

    await consume_async_queue(
        queue,
        shutdown_event=asyncio.Event(),
        process_item=_process,
        logger=logger,
        timeout=timeout,
    )
