"""SoAI - SoAIBench deferred tool activity bridge [backend/hardware/soaibench/deferred_tool_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tool_calls.deferred_tool_call_acceptance import (
    persist_deferred_tool_call_accepted_state,
)
from core.tool_calls.deferred_tool_call_signal import mark_result_deferred
from core.tool_calls.deferred_tool_call_streamer import (
    DeferredToolCallActivity,
    DeferredToolCallStreamer,
)
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from hardware.soaibench.responses import run_response
from hardware.soaibench.terminal_projection import terminal_projection
from hardware.soaibench.types import SoAIBenchRunStatus

if TYPE_CHECKING:
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.types.json import JSONDict

__all__ = (
    "finalize_soaibench_deferred_tool_activity",
    "finalize_soaibench_deferred_tool_activity_preserving",
    "mark_soaibench_deferred_tool_activity_accepted",
)

_OPERATION = "hardware.soaibench.deferred_tool_activity.finalize"


async def mark_soaibench_deferred_tool_activity_accepted(
    activity: DeferredToolCallActivity,
    *,
    owner_task_id: str,
    accepted_result: JSONDict,
) -> JSONDict:
    await persist_deferred_tool_call_accepted_state(
        database_tool_calls=activity.streamer_deps.database_tool_calls,
        storage_call_id=activity.storage_call_id,
        owner_task_id=owner_task_id,
        accepted_result=accepted_result,
    )
    return mark_result_deferred(
        accepted_result,
        owner_task_id=owner_task_id,
        accepted_state_persisted=True,
    )


async def finalize_soaibench_deferred_tool_activity_preserving(
    activity: DeferredToolCallActivity | None,
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    task_id: str,
) -> None:
    if activity is None:
        return
    try:
        await uncancel_then_cleanup(
            _finalize_soaibench_deferred_tool_activity(
                activity,
                database_hardware=database_hardware,
                run_id=run_id,
                task_id=task_id,
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=_OPERATION,
        )
        log_exception(
            activity.streamer_deps.logger,
            coerced,
            message="SoAIBench deferred tool activity finalization failed.",
            operation=_OPERATION,
            level="warning",
            details={"run_id": run_id, "task_id": task_id},
        )


async def finalize_soaibench_deferred_tool_activity(
    activity: DeferredToolCallActivity | None,
    *,
    run: JSONDict,
    task_id: str,
) -> None:
    if activity is None:
        return
    terminal_run = dict(run)
    terminal_run["task_id"] = task_id
    projection = terminal_projection(terminal_run)
    await DeferredToolCallStreamer(deps=activity.streamer_deps).finalize(
        status=projection.tool_status,
        duration_ms=_duration_ms(terminal_run),
        error_message=projection.tool_error_message,
        result_payload=run_response(terminal_run, accepted=False),
    )


async def _finalize_soaibench_deferred_tool_activity(
    activity: DeferredToolCallActivity,
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    task_id: str,
) -> None:
    run = await database_hardware.get_soaibench_run_for_user(
        user_id=activity.streamer_deps.user_id,
        run_id=run_id,
    )
    if run is None:
        raise StateError("SoAIBench deferred tool activity run was not found.")
    status_value = str(run.get("status") or "").strip()
    if status_value == SoAIBenchRunStatus.RUNNING.value:
        raise StateError("SoAIBench deferred tool activity cannot finalize a running run.")
    await finalize_soaibench_deferred_tool_activity(
        activity,
        run=run,
        task_id=task_id,
    )


def _duration_ms(run: JSONDict) -> int:
    duration_ms = coerce_optional_non_negative_int_strict(run.get("duration_ms"))
    if duration_ms is not None:
        return duration_ms
    completed_at_ms = coerce_optional_non_negative_int_strict(run.get("completed_at_ms"))
    started_at_ms = coerce_optional_non_negative_int_strict(run.get("started_at_ms"))
    if completed_at_ms is not None and started_at_ms is not None:
        return max(0, completed_at_ms - started_at_ms)
    return 0
