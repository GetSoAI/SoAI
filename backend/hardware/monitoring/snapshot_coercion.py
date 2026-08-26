"""SoAI - Hardware monitoring snapshot coercion helpers [backend/hardware/monitoring/snapshot_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent import futures

from core.errors.exceptions import SoAITimeoutError, StateError
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

__all__ = ("run_async_threadsafe_with_loop",)


def run_async_threadsafe_with_loop[T](
    coro: Coroutine[None, None, T],
    loop: asyncio.AbstractEventLoop | None,
) -> T:
    if loop and not loop.is_closed():
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is loop:
            raise StateError(
                "run_async_threadsafe_with_loop() cannot be called from the event loop thread.",
                operation="hardware.snapshot_coercion.run_async_threadsafe_with_loop",
            )
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=LOCAL_IO_TIMEOUT_SEC)
        except futures.TimeoutError as exception:
            future.cancel()
            raise SoAITimeoutError(
                "Timed out waiting for async snapshot read to complete.",
            ) from exception
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    raise StateError(
        "run_async_threadsafe_with_loop() requires an explicit target loop when called from async code.",
        operation="hardware.snapshot_coercion.run_async_threadsafe_with_loop",
    )
