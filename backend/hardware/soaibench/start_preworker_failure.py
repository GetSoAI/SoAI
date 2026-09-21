"""SoAI - SoAIBench pre-worker failure finalization [backend/hardware/soaibench/start_preworker_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.validation.numberish import require_int_from_numberish

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
    from hardware.soaibench.types import SoAIBenchRunStatus

__all__ = ("finish_preworker_failure_preserving",)

PREWORKER_FAILURE_OPERATION = "hardware.soaibench.start_cleanup.preworker_failure"


async def finish_preworker_failure_preserving(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    status: SoAIBenchRunStatus,
    reason: str | None,
    message: str,
    primary_exception: BaseException,
) -> JSONDict | None:
    try:
        return await uncancel_then_cleanup(
            _finish_preworker_failure(
                deps=deps,
                run=run,
                status=status,
                reason=reason,
                message=message,
            ),
        )
    except asyncio.CancelledError as cleanup_exception:
        primary_exception.add_note(
            f"SoAIBench pre-worker cleanup was cancelled: {cleanup_exception}",
        )
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(f"SoAIBench pre-worker cleanup failed: {cleanup_exception}")
        coerced_exception = coerce_to_soai_error(
            cleanup_exception,
            operation=PREWORKER_FAILURE_OPERATION,
        )
        log_exception(
            deps.logger,
            coerced_exception,
            message="SoAIBench pre-worker cleanup failed.",
            operation=PREWORKER_FAILURE_OPERATION,
            level="warning",
        )
    return None


async def _finish_preworker_failure(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    status: SoAIBenchRunStatus,
    reason: str | None,
    message: str,
) -> JSONDict:
    completed_at_ms = epoch_ms()
    started_at_ms = require_int_from_numberish(run["started_at_ms"], field="started_at_ms")
    mutation = await deps.database_hardware.finish_soaibench_run(
        str(run["run_id"]),
        {
            "status": status.value,
            "completed_at_ms": completed_at_ms,
            "duration_ms": max(0, completed_at_ms - started_at_ms),
            "sample_count": 0,
            "summary_json": serialize_json_compact_stable({"message": message}),
            "failure_reason": reason,
        },
    )
    if mutation.run is None:
        raise StateError("SoAIBench pre-worker terminal row was not materialized.")
    return mutation.run
