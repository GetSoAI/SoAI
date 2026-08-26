"""SoAI - SoAIBench active run cancellation helpers [backend/hardware/soaibench/service_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tasks.task_cancellation import request_task_cancellation

if TYPE_CHECKING:
    from hardware.soaibench.active_runs import ActiveSoAIBenchRuns
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = ("cancel_active_soaibench_runs",)


async def cancel_active_soaibench_runs(
    *,
    deps: SoAIBenchServiceDependencies,
    active_runs: ActiveSoAIBenchRuns,
    reason: str,
    operation: str,
    cancelled_message: str,
) -> None:
    runs = active_runs.all_runs()
    for active in runs:
        active.stop_event.set()
        try:
            await request_task_cancellation(
                deps.task_registry,
                active.task_id,
                reason=reason,
            )
        except asyncio.CancelledError as exception:
            exception.add_note("SoAIBench active run cancellation was cancelled.")
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced_exception = coerce_to_soai_error(
                exception,
                operation=operation,
            )
            log_exception(
                deps.logger,
                coerced_exception,
                message="SoAIBench active run cancellation request failed.",
                operation=operation,
                details={"run_id": active.run_id, "task_id": active.task_id},
                level="warning",
            )
    for active in runs:
        worker = active.worker
        if worker is None or worker.done():
            continue
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            deps.logger.info(cancelled_message, extra={"run_id": active.run_id})
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced_exception = coerce_to_soai_error(
                exception,
                operation=operation,
            )
            log_exception(
                deps.logger,
                coerced_exception,
                message="SoAIBench active worker cancellation failed.",
                operation=operation,
                details={"run_id": active.run_id, "task_id": active.task_id},
                level="warning",
            )
