"""SoAI - Media operation cancellation token racing [backend/core/media/cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING

from core.concurrency.task_groups import cancel_and_await
from core.errors.exceptions import SoAITimeoutError, StateError
from core.tasks.awaitable_cleanup import try_close_unawaited

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = ("await_media_operation",)


async def await_media_operation[T](
    operation: Coroutine[None, None, T],
    cancellation_token: CancellationTokenProtocol | None,
    *,
    extraction_deadline: float,
) -> T:
    remaining_seconds = extraction_deadline - asyncio.get_running_loop().time()
    if remaining_seconds <= 0:
        try_close_unawaited(operation)
        raise SoAITimeoutError("Media extraction deadline exceeded.")
    if cancellation_token is None:
        try:
            return await asyncio.wait_for(operation, timeout=remaining_seconds)
        except TimeoutError as exception:
            raise SoAITimeoutError(
                "Media extraction deadline exceeded.",
                cause=exception,
            ) from exception
    cancellation_token.raise_if_cancelled()
    operation_task = asyncio.create_task(operation, name="media-operation")
    cancellation_task = asyncio.create_task(
        cancellation_token.wait(),
        name=f"media-cancellation:{cancellation_token.cancellation_id}",
    )
    try:
        done, _pending = await asyncio.wait(
            (operation_task, cancellation_task),
            return_when=asyncio.FIRST_COMPLETED,
            timeout=remaining_seconds,
        )
        if operation_task in done:
            return await operation_task
        if cancellation_task not in done:
            raise SoAITimeoutError("Media extraction deadline exceeded.")
        operation_task.cancel()
        await cancel_and_await((operation_task,), task_label="media operation")
        cancellation_token.raise_if_cancelled()
        raise StateError("Media cancellation watcher completed without cancellation.")
    finally:
        await cancel_and_await(
            (operation_task, cancellation_task),
            task_label="media operation race",
        )
