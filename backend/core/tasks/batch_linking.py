"""SoAI - Batch task linking cancellation helper [backend/core/tasks/batch_linking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("cancel_unbound_batch_tasks",)


async def cancel_unbound_batch_tasks(
    task_specs: list[tuple[str, asyncio.Task[None], str, dict[str, JSONValue] | None]],
    bound_count: int,
) -> None:
    pending: list[asyncio.Task[None]] = []
    for _, unbound_task, _, _ in task_specs[bound_count:]:
        if not unbound_task.done():
            unbound_task.cancel()
            pending.append(unbound_task)
    if pending:
        cleanup_results = await asyncio.gather(*pending, return_exceptions=True)
        for cleanup_result in cleanup_results:
            if isinstance(cleanup_result, asyncio.CancelledError):
                continue
            if isinstance(cleanup_result, BaseException):
                raise cleanup_result
