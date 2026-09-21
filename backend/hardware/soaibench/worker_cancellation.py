"""SoAI - SoAIBench worker cancellation cleanup [backend/hardware/soaibench/worker_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from hardware.soaibench.worker_runtime_conditions import (
    finish_cancelled_runtime_profile,
)

if TYPE_CHECKING:
    from hardware.soaibench.types import SoAIBenchProfile
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext

__all__ = ("finish_direct_cancellation_preserving",)

LOGGER_NAME = "SoAI.hardware.soaibench.worker_cancellation"
CANCELLATION_CLEANUP_OPERATION = "hardware.soaibench.worker.cancellation_cleanup"


async def finish_direct_cancellation_preserving(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    profile: SoAIBenchProfile,
    primary_exception: asyncio.CancelledError,
) -> None:
    try:
        await uncancel_then_cleanup(
            finish_cancelled_runtime_profile(
                runtime_context=runtime_context,
                profile=profile,
            ),
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
