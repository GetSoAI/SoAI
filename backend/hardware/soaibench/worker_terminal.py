"""SoAI - SoAIBench worker terminal persistence [backend/hardware/soaibench/worker_terminal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.timing.epoch import epoch_ms
from hardware.soaibench.errors import SoAIBenchUnsupported, unsupported_guidance
from hardware.soaibench.types import SoAIBenchProfile, SoAIBenchRunStatus

if TYPE_CHECKING:
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict
    from hardware.soaibench.workload import SoAIBenchWorkloadResult

__all__ = (
    "finish_cancelled",
    "finish_failure",
    "finish_success",
    "finish_unstable",
    "finish_unsupported",
)


async def finish_success(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    status: SoAIBenchRunStatus,
    task_status: TaskStatus,
    started_at_ms: int,
    base_summary: JSONDict,
    result: SoAIBenchWorkloadResult,
    sample_count: int,
    failure_reason: str | None = None,
    terminal_fields: JSONDict | None = None,
) -> None:
    completed_at_ms = epoch_ms()
    fields = {
        **result.score_fields,
        "status": status.value,
        "completed_at_ms": completed_at_ms,
        "last_heartbeat_at_ms": completed_at_ms,
        "duration_ms": max(result.duration_ms, completed_at_ms - started_at_ms),
        "sample_count": sample_count,
        "summary_json": serialize_json_compact_stable({**base_summary, **result.summary}),
        "failure_reason": failure_reason,
    }
    if terminal_fields is not None:
        fields.update(terminal_fields)
    await database_hardware.finish_soaibench_run(run_id, fields)
    await finalize(
        task_registry,
        task_id,
        task_status,
        result={"run_id": run_id, "status": status.value, "score": result.score_fields},
        status_message=_success_status_message(status),
    )


async def finish_cancelled(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    profile: SoAIBenchProfile,
    stop_event: asyncio.Event,
) -> None:
    status = (
        SoAIBenchRunStatus.STOPPED
        if profile == SoAIBenchProfile.STRESS and stop_event.is_set()
        else SoAIBenchRunStatus.CANCELLED
    )
    await finish_terminal_without_score(
        database_hardware=database_hardware,
        task_registry=task_registry,
        run_id=run_id,
        task_id=task_id,
        started_at_ms=started_at_ms,
        base_summary=base_summary,
        status=status,
        task_status=TaskStatus.CANCELLED,
        failure_reason=None,
        unsupported_reason=None,
        error_message=None,
    )


async def finish_unsupported(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    exception: SoAIBenchUnsupported,
) -> None:
    summary = {
        **base_summary,
        "message": exception.message,
        "guidance": unsupported_guidance(exception.reason),
    }
    await finish_terminal_without_score(
        database_hardware=database_hardware,
        task_registry=task_registry,
        run_id=run_id,
        task_id=task_id,
        started_at_ms=started_at_ms,
        base_summary=summary,
        status=SoAIBenchRunStatus.UNSUPPORTED,
        task_status=TaskStatus.FAILED,
        failure_reason=None,
        unsupported_reason=exception.reason,
        error_message=exception.message,
    )


async def finish_unstable(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    reason: str,
    message: str,
) -> None:
    await finish_terminal_without_score(
        database_hardware=database_hardware,
        task_registry=task_registry,
        run_id=run_id,
        task_id=task_id,
        started_at_ms=started_at_ms,
        base_summary={**base_summary, "message": message},
        status=SoAIBenchRunStatus.UNSTABLE,
        task_status=TaskStatus.FAILED,
        failure_reason=reason,
        unsupported_reason=None,
        error_message=message,
    )


async def finish_failure(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    reason: str,
    message: str,
) -> None:
    await finish_terminal_without_score(
        database_hardware=database_hardware,
        task_registry=task_registry,
        run_id=run_id,
        task_id=task_id,
        started_at_ms=started_at_ms,
        base_summary={**base_summary, "message": message},
        status=SoAIBenchRunStatus.FAILED,
        task_status=TaskStatus.FAILED,
        failure_reason=reason,
        unsupported_reason=None,
        error_message=message,
    )


async def finish_terminal_without_score(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    status: SoAIBenchRunStatus,
    task_status: TaskStatus,
    failure_reason: str | None,
    unsupported_reason: str | None,
    error_message: str | None,
) -> None:
    completed_at_ms = epoch_ms()
    await database_hardware.finish_soaibench_run(
        run_id,
        {
            "status": status.value,
            "completed_at_ms": completed_at_ms,
            "last_heartbeat_at_ms": completed_at_ms,
            "duration_ms": max(0, completed_at_ms - started_at_ms),
            "sample_count": 0,
            "summary_json": serialize_json_compact_stable(base_summary),
            "failure_reason": failure_reason,
            "unsupported_reason": unsupported_reason,
        },
    )
    await finalize(
        task_registry,
        task_id,
        task_status,
        result={"run_id": run_id, "status": status.value},
        error_message=error_message,
    )


def _success_status_message(status: SoAIBenchRunStatus) -> str:
    if status == SoAIBenchRunStatus.STOPPED:
        return "SoAIBench stopped."
    if status == SoAIBenchRunStatus.UNSTABLE:
        return "SoAIBench unstable."
    return "SoAIBench completed."
