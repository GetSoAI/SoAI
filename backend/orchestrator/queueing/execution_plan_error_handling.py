"""SoAI - Execution plan reservation error handling [backend/orchestrator/queueing/execution_plan_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.orchestrator.protocols_queue import QueueExecutionReservationsProtocol
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "release_execution_plan_reservation_after_cancellation",
    "run_execution_plan_with_reservation_guard",
)


async def release_execution_plan_reservation_after_cancellation(
    *,
    reservations: QueueExecutionReservationsProtocol,
    tracking_id: str,
) -> None:
    await reservations.release(tracking_id)


async def run_execution_plan_with_reservation_guard[ExecutionPlanResult](
    *,
    operation: str,
    message: str,
    logger: LoggerProtocol,
    reservations: QueueExecutionReservationsProtocol,
    tracking_id: str,
    details: JSONDict,
    awaitable: Awaitable[ExecutionPlanResult],
) -> ExecutionPlanResult:
    try:
        return await awaitable
    except asyncio.CancelledError:
        await release_execution_plan_reservation_after_cancellation(
            reservations=reservations,
            tracking_id=tracking_id,
        )
        raise
    except Exception as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=operation,
        )
        log_exception(
            logger,
            coerced,
            message=message,
            operation=operation,
            details=details,
        )
        await reservations.release(tracking_id)
        raise
