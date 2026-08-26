"""SoAI - Automation worker queue runtime [backend/app/background/automation_worker_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.background.runtime_api_dependencies import resolve_api_dependencies_from_runtime
from core.automation.automation_identifiers import build_automation_run_cancellation_id
from core.concurrency.task_groups import QueueEventWaiter, QueueWaitResult
from core.errors.exceptions import StateError
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.periodic import wait_for_periodic_tick
from features.automation.executor import execute_automation_run

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.runtime.protocols import RuntimeStateStoreProtocol

__all__ = (
    "run_automation_worker_loop",
    "wait_for_automation_tick",
)


async def wait_for_automation_tick(
    *,
    shutdown_event: asyncio.Event,
    wake_event: asyncio.Event,
    tick_seconds: float,
) -> bool:
    return await wait_for_periodic_tick(
        stop_event=shutdown_event,
        interval_seconds=tick_seconds,
        wake_event=wake_event,
    )


async def run_automation_worker_loop(
    *,
    runtime_state: RuntimeStateStoreProtocol,
    run_queue: asyncio.Queue[str],
    queued_run_ids: set[str],
    shutdown_event: asyncio.Event,
    refill_run_queue: Callable[[], None] | None = None,
    worker_index: int,
) -> None:
    api_dependencies = await resolve_api_dependencies_from_runtime(runtime_state)
    waiter = QueueEventWaiter(run_queue, shutdown_event)
    while not shutdown_event.is_set():
        result = await waiter.wait_with_result()
        if not result.retrieved_from_queue:
            continue
        run_id = _require_run_id(result)
        if shutdown_event.is_set():
            run_queue.task_done()
            queued_run_ids.discard(run_id)
            continue
        try:
            async with cancellation_token_scope(
                api_dependencies.token_collection,
                api_dependencies.cancellation_history,
                api_dependencies.cancellation_event_bus,
                cancellation_id=build_automation_run_cancellation_id(run_id),
                owner=f"automation-worker-{worker_index}",
                metadata={"run_id": run_id, "worker_index": worker_index},
            ):
                await execute_automation_run(api_dependencies, run_id=run_id)
        finally:
            run_queue.task_done()
            queued_run_ids.discard(run_id)
            if refill_run_queue is not None:
                refill_run_queue()


def _require_run_id(result: QueueWaitResult[str]) -> str:
    event = result.event
    if not isinstance(event, str) or not event.strip():
        raise StateError("Automation worker queue item is invalid.")
    return event.strip()
