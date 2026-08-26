"""SoAI - SoAIBench worker lifecycle [backend/hardware/soaibench/worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import (
    BoundedBlockingCancelledBase,
    BoundedBlockingTimeoutBase,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.validation.numberish import require_int_from_numberish
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.events import publish_soaibench_worker_update
from hardware.soaibench.gpu_identity import identity_from_payload
from hardware.soaibench.types import SoAIBenchBenchmarkMode, SoAIBenchProfile
from hardware.soaibench.worker_cancellation import (
    finish_direct_cancellation_preserving,
    wait_for_blocking_completion,
)
from hardware.soaibench.worker_context import (
    SoAIBenchWorkerEventContext,
    SoAIBenchWorkerRuntimeContext,
)
from hardware.soaibench.worker_inputs import (
    base_summary_from_run,
    temperature_limit_from_summary,
)
from hardware.soaibench.worker_profiles import run_selected_profile
from hardware.soaibench.worker_terminal import (
    finish_failure,
    finish_unstable,
    finish_unsupported,
)

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols import HardwareManagerProtocol
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = ("run_soaibench_worker",)

UNSTABLE_FAILURE_REASONS: tuple[str, ...] = ("opencl_checksum_failed", "opencl_device_lost")
WORKER_OPERATION = "hardware.soaibench.worker"


async def run_soaibench_worker(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    hardware_manager: HardwareManagerProtocol,
    opencl_pool: BoundedBlockingPool,
    run: JSONDict,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    stop_event: asyncio.Event,
) -> None:
    profile = SoAIBenchProfile(str(run["profile"]))
    benchmark_mode = SoAIBenchBenchmarkMode(str(run.get("benchmark_mode") or "quick"))
    identity = identity_from_payload(run)
    started_at_ms = require_int_from_numberish(run["started_at_ms"], field="started_at_ms")
    user_id = require_int_from_numberish(run["created_by_user_id"], field="created_by_user_id")
    base_summary = base_summary_from_run(run)
    temperature_limit_celsius = temperature_limit_from_summary(base_summary)
    runtime_context = SoAIBenchWorkerRuntimeContext(
        database_hardware=database_hardware,
        hardware_manager=hardware_manager,
        task_registry=task_registry,
        run_id=run_id,
        task_id=task_id,
        identity=identity,
        started_at_ms=started_at_ms,
        base_summary=base_summary,
        temperature_limit_celsius=temperature_limit_celsius,
        stop_event=stop_event,
    )
    event_context = SoAIBenchWorkerEventContext(
        database_hardware=database_hardware,
        event_bus=event_bus,
        logger=logger,
        user_id=user_id,
        run_id=run_id,
        task_id=task_id,
    )
    try:
        await run_selected_profile(
            opencl_pool=opencl_pool,
            runtime_context=runtime_context,
            event_context=event_context,
            profile=profile,
            benchmark_mode=benchmark_mode,
        )
    except BoundedBlockingCancelledBase as exception:
        await wait_for_blocking_completion(exception, logger)
        await finish_direct_cancellation_preserving(
            runtime_context=runtime_context,
            profile=profile,
            primary_exception=exception,
        )
        await publish_soaibench_worker_update(event_context, "shutdown_cancelled")
        raise
    except BoundedBlockingTimeoutBase as exception:
        await wait_for_blocking_completion(exception, logger)
        await finish_failure(
            database_hardware=database_hardware,
            task_registry=task_registry,
            run_id=run_id,
            task_id=task_id,
            started_at_ms=started_at_ms,
            base_summary=base_summary,
            reason="opencl_runtime_error",
            message="SoAIBench OpenCL workload timed out.",
        )
        await publish_soaibench_worker_update(event_context, "terminal")
    except asyncio.CancelledError as exception:
        await finish_direct_cancellation_preserving(
            runtime_context=runtime_context,
            profile=profile,
            primary_exception=exception,
        )
        await publish_soaibench_worker_update(event_context, "shutdown_cancelled")
        raise
    except SoAIBenchUnsupported as exception:
        if exception.reason in UNSTABLE_FAILURE_REASONS:
            await finish_unstable(
                database_hardware=database_hardware,
                task_registry=task_registry,
                run_id=run_id,
                task_id=task_id,
                started_at_ms=started_at_ms,
                base_summary=base_summary,
                reason=exception.reason,
                message=exception.message,
            )
            await publish_soaibench_worker_update(event_context, "terminal")
            return
        await finish_unsupported(
            database_hardware=database_hardware,
            task_registry=task_registry,
            run_id=run_id,
            task_id=task_id,
            started_at_ms=started_at_ms,
            base_summary=base_summary,
            exception=exception,
        )
        await publish_soaibench_worker_update(event_context, "terminal")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="SoAIBench recoverable worker failure.",
            operation=WORKER_OPERATION,
        )
        await finish_failure(
            database_hardware=database_hardware,
            task_registry=task_registry,
            run_id=run_id,
            task_id=task_id,
            started_at_ms=started_at_ms,
            base_summary=base_summary,
            reason="opencl_runtime_error",
            message=str(exception),
        )
        await publish_soaibench_worker_update(event_context, "terminal")
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(
            exception,
            operation=WORKER_OPERATION,
        )
        log_exception(
            logger,
            coerced_exception,
            message="SoAIBench worker failure.",
            operation=WORKER_OPERATION,
        )
        await finish_failure(
            database_hardware=database_hardware,
            task_registry=task_registry,
            run_id=run_id,
            task_id=task_id,
            started_at_ms=started_at_ms,
            base_summary=base_summary,
            reason="opencl_runtime_error",
            message=str(exception),
        )
        await publish_soaibench_worker_update(event_context, "terminal")
