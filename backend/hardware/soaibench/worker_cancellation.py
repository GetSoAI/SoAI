"""SoAI - SoAIBench worker cancellation cleanup [backend/hardware/soaibench/worker_cancellation.py]"""
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
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from hardware.soaibench.worker_runtime_conditions import (
    finish_cancelled_runtime_profile,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from hardware.soaibench.types import SoAIBenchProfile
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext

__all__ = (
    "finish_direct_cancellation_preserving",
    "wait_for_blocking_completion",
)

BLOCKING_COMPLETION_GRACE_SECONDS = 2.0
LOGGER_NAME = "SoAI.hardware.soaibench.worker_cancellation"
BLOCKING_COMPLETION_OPERATION = "hardware.soaibench.worker.blocking_completion"
CANCELLATION_CLEANUP_OPERATION = "hardware.soaibench.worker.cancellation_cleanup"


async def wait_for_blocking_completion(
    exception: BoundedBlockingCancelledBase | BoundedBlockingTimeoutBase,
    logger: LoggerProtocol,
) -> None:
    current_task = asyncio.current_task()
    if current_task is not None:
        while current_task.cancelling():
            current_task.uncancel()
    try:
        await exception.wait_for_completion(BLOCKING_COMPLETION_GRACE_SECONDS)
    except asyncio.CancelledError as future_exception:
        log_exception(
            logger,
            future_exception,
            message="SoAIBench blocking workload future was cancelled.",
            operation=BLOCKING_COMPLETION_OPERATION,
            level="warning",
        )
    except TimeoutError as future_exception:
        log_exception(
            logger,
            future_exception,
            message="SoAIBench blocking workload did not finish within the cancellation grace period.",
            operation=BLOCKING_COMPLETION_OPERATION,
            level="warning",
        )
    except HANDLED_RUNTIME_EXCEPTIONS as future_exception:
        coerced_exception = coerce_to_soai_error(
            future_exception,
            operation=BLOCKING_COMPLETION_OPERATION,
        )
        log_exception(
            logger,
            coerced_exception,
            message="SoAIBench blocking workload ended after cancellation.",
            operation=BLOCKING_COMPLETION_OPERATION,
            level="warning",
        )


async def finish_direct_cancellation_preserving(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    profile: SoAIBenchProfile,
    primary_exception: asyncio.CancelledError,
) -> None:
    current_task = asyncio.current_task()
    if current_task is not None:
        while current_task.cancelling():
            current_task.uncancel()
    try:
        await finish_cancelled_runtime_profile(
            runtime_context=runtime_context,
            profile=profile,
        )
    except asyncio.CancelledError as cleanup_exception:
        primary_exception.add_note(
            f"SoAIBench cancellation cleanup was cancelled: {cleanup_exception}",
        )
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(f"SoAIBench cancellation cleanup failed: {cleanup_exception}")
        coerced_exception = coerce_to_soai_error(
            cleanup_exception,
            operation=CANCELLATION_CLEANUP_OPERATION,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced_exception,
            message="SoAIBench cancellation cleanup failed.",
            operation=CANCELLATION_CLEANUP_OPERATION,
            level="warning",
        )
