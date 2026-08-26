"""SoAI - SoAIBench failed registration cleanup [backend/hardware/soaibench/registration_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

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
) -> None:
    current_task = asyncio.current_task()
    if current_task is not None:
        while current_task.cancelling():
            current_task.uncancel()
    try:
        await _finish_start_registration_failed(
            context=context,
            native_task_created=native_task_created,
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
) -> None:
    completed_at_ms = epoch_ms()
    try:
        await context.deps.database_hardware.finish_soaibench_run(
            context.run_id,
            {
                "status": SoAIBenchRunStatus.FAILED.value,
                "completed_at_ms": completed_at_ms,
                "duration_ms": 0,
                "sample_count": 0,
                "summary_json": serialize_json_compact_stable(
                    {"failure_reason": "start_registration_failed"},
                ),
                "failure_reason": "start_registration_failed",
            },
        )
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
                    TaskStatus.FAILED,
                    result={
                        "run_id": context.run_id,
                        "status": SoAIBenchRunStatus.FAILED.value,
                    },
                    error_message="SoAIBench worker registration failed.",
                )
        finally:
            await publish_soaibench_run_update(
                database_hardware=context.deps.database_hardware,
                event_bus=context.deps.event_bus,
                logger=context.deps.logger,
                user_id=context.user_id,
                run_id=context.run_id,
                update_type="terminal",
                task_id=context.task_id if native_task_created else None,
            )
    finally:
        context.active_runs.unbind(run_id=context.run_id, lease_id=context.lease_id)
        await context.deps.activity_registry.release(
            device_id=context.device_id,
            lease_id=context.lease_id,
        )
