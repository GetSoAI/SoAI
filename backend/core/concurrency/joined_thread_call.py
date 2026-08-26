"""SoAI - Cancellation-safe joined calls on the default thread pool [backend/core/concurrency/joined_thread_call.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS

__all__ = ("run_joined_thread_call",)


async def run_joined_thread_call[*Arguments, Result, CleanupResult](
    function: Callable[[*Arguments], Result],
    *arguments: *Arguments,
    task_name: str,
    cancelled_result_cleanup: Callable[[Result], CleanupResult] | None = None,
) -> Result:
    thread_task = asyncio.create_task(
        asyncio.to_thread(function, *arguments),
        name=task_name,
    )
    try:
        return await asyncio.shield(thread_task)
    except asyncio.CancelledError as exception:
        try:
            result = await uncancel_then_cleanup(thread_task)
        except HANDLED_RUNTIME_EXCEPTIONS as completion_exception:
            exception.add_note(f"Joined thread completion failed: {completion_exception}")
        else:
            if cancelled_result_cleanup is not None:
                try:
                    cancelled_result_cleanup(result)
                except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
                    exception.add_note(f"Joined thread result cleanup failed: {cleanup_exception}")
        raise
