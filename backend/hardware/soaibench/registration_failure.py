"""SoAI - SoAIBench failed registration cleanup [backend/hardware/soaibench/registration_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.timing.epoch import epoch_ms
from hardware.soaibench.deferred_tool_activity import (
    finalize_soaibench_deferred_tool_activity_preserving,
)
from hardware.soaibench.events import publish_soaibench_run_update
from hardware.soaibench.types import SoAIBenchRunStatus

if TYPE_CHECKING:
    from hardware.soaibench.registration_context import SoAIBenchRegistrationContext

__all__ = ("finish_start_registration_failed_preserving",)

REGISTRATION_CLEANUP_OPERATION = "hardware.soaibench.registration.cleanup"


async def finish_start_registration_failed_preserving(
    *,
    context: SoAIBenchRegistrationContext,
    native_task_created: bool,
    primary_exception: BaseException,
    status: SoAIBenchRunStatus = SoAIBenchRunStatus.FAILED,
    failure_reason: str | None = "start_registration_failed",
    message: str = "SoAIBench worker registration failed.",
    retain_degraded_lease: bool = False,
) -> None:
    try:
        await uncancel_then_cleanup(
            _finish_start_registration_failed(
                context=context,
                native_task_created=native_task_created,
                status=status,
                failure_reason=failure_reason,
                message=message,
                retain_degraded_lease=retain_degraded_lease,
            ),
        )
    except asyncio.CancelledError as cleanup_exception:
        primary_exception.add_note(
            f"SoAIBench registration cleanup was cancelled: {cleanup_exception}",
        )
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(f"SoAIBench registration cleanup failed: {cleanup_exception}")
        coerced_exception = coerce_to_soai_error(
            cleanup_exception,
            operation=REGISTRATION_CLEANUP_OPERATION,
        )
        log_exception(
            context.deps.logger,
            coerced_exception,
            message="SoAIBench registration cleanup failed.",
            operation=REGISTRATION_CLEANUP_OPERATION,
            level="warning",
        )


async def _finish_start_registration_failed(
    *,
    context: SoAIBenchRegistrationContext,
    native_task_created: bool,
    status: SoAIBenchRunStatus,
    failure_reason: str | None,
    message: str,
    retain_degraded_lease: bool,
) -> None:
    completed_at_ms = epoch_ms()
    terminal_persistence_verified = False
    try:
        mutation = await context.deps.database_hardware.finish_soaibench_run(
            context.run_id,
            {
                "status": status.value,
                "completed_at_ms": completed_at_ms,
                "duration_ms": 0,
                "sample_count": 0,
                "summary_json": serialize_json_compact_stable(
                    {"message": message},
                ),
                "failure_reason": failure_reason,
            },
        )
        terminal_persistence_verified = True
        try:
            await finalize_soaibench_deferred_tool_activity_preserving(
                context.deferred_tool_activity,
                database_hardware=context.deps.database_hardware,
                run_id=context.run_id,
                task_id=context.task_id,
            )
            if native_task_created:
                await finalize(
                    context.deps.task_registry,
                    context.task_id,
                    (
                        TaskStatus.CANCELLED
                        if status == SoAIBenchRunStatus.CANCELLED
                        else TaskStatus.FAILED
                    ),
                    result={
                        "run_id": context.run_id,
                        "status": status.value,
                    },
                    error_message=message,
                )
        finally:
            if mutation.run is not None:
                await publish_soaibench_run_update(
                    event_bus=context.deps.event_bus,
                    logger=context.deps.logger,
                    run=mutation.run,
                    update_type="terminal",
                    task_id=context.task_id if native_task_created else None,
                )
    finally:
        context.active_runs.unbind(run_id=context.run_id, lease_id=context.lease_id)
        if retain_degraded_lease or not terminal_persistence_verified:
            await context.deps.activity_registry.mark_degraded(
                device_id=context.device_id,
                lease_id=context.lease_id,
                reason=(
                    "SoAIBench OpenCL child exit could not be verified."
                    if retain_degraded_lease
                    else "SoAIBench terminal persistence could not be verified."
                ),
            )
        else:
            await context.deps.activity_registry.release(
                device_id=context.device_id,
                lease_id=context.lease_id,
            )
