"""SoAI - SoAIBench worker terminal persistence [backend/hardware/soaibench/worker_terminal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from hardware.soaibench.errors import (
    SoAIBenchUnsupported,
    unsupported_guidance,
)
from hardware.soaibench.types import (
    SOAIBENCH_SCORE_VERSION,
    SoAIBenchProfile,
    SoAIBenchRunStatus,
)

if TYPE_CHECKING:
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.types.json import JSONDict
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext
    from hardware.soaibench.workload import SoAIBenchWorkloadResult

__all__ = (
    "finish_cancelled",
    "finish_failure",
    "finish_success",
    "finish_successful_runtime",
    "finish_unstable",
    "finish_unsupported",
)


async def finish_success(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    status: SoAIBenchRunStatus,
    started_at_ms: int,
    base_summary: JSONDict,
    result: SoAIBenchWorkloadResult,
    sample_count: int,
    failure_reason: str | None = None,
    terminal_fields: JSONDict | None = None,
) -> JSONDict:
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
    mutation = await database_hardware.finish_soaibench_run(run_id, fields)
    return _require_durable_run(mutation.run)


async def finish_successful_runtime(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    status: SoAIBenchRunStatus,
    base_summary: JSONDict,
    result: SoAIBenchWorkloadResult,
    sample_count: int,
    failure_reason: str | None = None,
    terminal_fields: JSONDict | None = None,
) -> None:
    terminal_run = await finish_success(
        database_hardware=runtime_context.database_hardware,
        run_id=runtime_context.run_id,
        status=status,
        started_at_ms=runtime_context.started_at_ms,
        base_summary=base_summary,
        result=result,
        sample_count=sample_count,
        failure_reason=failure_reason,
        terminal_fields=terminal_fields,
    )
    runtime_context.state.current_run = terminal_run
    runtime_context.state.terminal_run = terminal_run


async def finish_cancelled(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    profile: SoAIBenchProfile,
    stop_event: asyncio.Event,
) -> JSONDict:
    status = (
        SoAIBenchRunStatus.STOPPED
        if profile == SoAIBenchProfile.STRESS and stop_event.is_set()
        else SoAIBenchRunStatus.CANCELLED
    )
    return await finish_terminal_without_score(
        database_hardware=database_hardware,
        run_id=run_id,
        started_at_ms=started_at_ms,
        base_summary=base_summary,
        status=status,
        failure_reason=None,
        unsupported_reason=None,
    )


async def finish_unsupported(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    exception: SoAIBenchUnsupported,
) -> JSONDict:
    summary = {
        **base_summary,
        "message": exception.message,
        "guidance": unsupported_guidance(exception.reason),
    }
    return await finish_terminal_without_score(
        database_hardware=database_hardware,
        run_id=run_id,
        started_at_ms=started_at_ms,
        base_summary=summary,
        status=SoAIBenchRunStatus.UNSUPPORTED,
        failure_reason=None,
        unsupported_reason=exception.reason,
    )


async def finish_unstable(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    reason: str,
    message: str,
) -> JSONDict:
    return await finish_terminal_without_score(
        database_hardware=database_hardware,
        run_id=run_id,
        started_at_ms=started_at_ms,
        base_summary={**base_summary, "message": message},
        status=SoAIBenchRunStatus.UNSTABLE,
        failure_reason=reason,
        unsupported_reason=None,
    )


async def finish_failure(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    reason: str,
    message: str,
) -> JSONDict:
    return await finish_terminal_without_score(
        database_hardware=database_hardware,
        run_id=run_id,
        started_at_ms=started_at_ms,
        base_summary={**base_summary, "message": message},
        status=SoAIBenchRunStatus.FAILED,
        failure_reason=reason,
        unsupported_reason=None,
    )


async def finish_terminal_without_score(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    run_id: str,
    started_at_ms: int,
    base_summary: JSONDict,
    status: SoAIBenchRunStatus,
    failure_reason: str | None,
    unsupported_reason: str | None,
) -> JSONDict:
    completed_at_ms = epoch_ms()
    mutation = await database_hardware.finish_soaibench_run(
        run_id,
        {
            "status": status.value,
            "score_version": SOAIBENCH_SCORE_VERSION,
            "completed_at_ms": completed_at_ms,
            "last_heartbeat_at_ms": completed_at_ms,
            "duration_ms": max(0, completed_at_ms - started_at_ms),
            "sample_count": 0,
            "summary_json": serialize_json_compact_stable(base_summary),
            "failure_reason": failure_reason,
            "unsupported_reason": unsupported_reason,
        },
    )
    return _require_durable_run(mutation.run)


def _require_durable_run(run: JSONDict | None) -> JSONDict:
    if run is None:
        raise StateError("SoAIBench terminal mutation did not return a durable run.")
    return run
