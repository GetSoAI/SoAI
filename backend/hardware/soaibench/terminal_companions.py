"""SoAI - SoAIBench durable terminal companions [backend/hardware/soaibench/terminal_companions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tasks.finalization import finalize
from hardware.soaibench.deferred_tool_activity import (
    finalize_soaibench_deferred_tool_activity,
)
from hardware.soaibench.errors import (
    SoAIBenchCompanionFailure,
    SoAIBenchCompanionFinalizationError,
)
from hardware.soaibench.events import publish_soaibench_worker_update
from hardware.soaibench.terminal_projection import terminal_projection

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
    from core.types.json import JSONDict
    from hardware.soaibench.worker_context import SoAIBenchWorkerEventContext

__all__ = ("finalize_soaibench_terminal_companions",)

COMPANION_FAILURE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


async def finalize_soaibench_terminal_companions(
    *,
    event_context: SoAIBenchWorkerEventContext,
    task_registry: TaskRegistryProtocol,
    deferred_tool_activity: DeferredToolCallActivity | None,
    run: JSONDict,
) -> None:
    await uncancel_then_cleanup(
        _finalize_terminal_companions(
            event_context=event_context,
            task_registry=task_registry,
            deferred_tool_activity=deferred_tool_activity,
            run=run,
        ),
    )


async def _finalize_terminal_companions(
    *,
    event_context: SoAIBenchWorkerEventContext,
    task_registry: TaskRegistryProtocol,
    deferred_tool_activity: DeferredToolCallActivity | None,
    run: JSONDict,
) -> None:
    failures: list[SoAIBenchCompanionFailure] = []
    try:
        await publish_soaibench_worker_update(event_context, run, "terminal")
    except COMPANION_FAILURE_EXCEPTIONS as exception:
        failures.append(SoAIBenchCompanionFailure("event", exception))
    projection = terminal_projection(run)
    try:
        await finalize(
            task_registry,
            event_context.task_id,
            projection.task_status,
            result=projection.task_result,
            error_message=projection.error_message,
            status_message=projection.status_message,
        )
    except COMPANION_FAILURE_EXCEPTIONS as exception:
        failures.append(SoAIBenchCompanionFailure("task", exception))
    try:
        await finalize_soaibench_deferred_tool_activity(
            deferred_tool_activity,
            run=run,
            task_id=event_context.task_id,
        )
    except COMPANION_FAILURE_EXCEPTIONS as exception:
        failures.append(SoAIBenchCompanionFailure("deferred_tool", exception))
    if failures:
        raise SoAIBenchCompanionFinalizationError(run, tuple(failures))
