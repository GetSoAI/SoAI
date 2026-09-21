"""SoAI - SoAIBench realtime event publishing [backend/hardware/soaibench/events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import EventDelivery
from core.events.types_system import SoAIBenchRunUpdatedEvent
from core.validation.integers import coerce_non_negative_exact_int_or_zero
from core.validation.numberish import require_int_from_numberish
from hardware.soaibench.responses import run_response

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from hardware.soaibench.worker_context import SoAIBenchWorkerEventContext

__all__ = ("publish_soaibench_run_update", "publish_soaibench_worker_update")

HEARTBEAT_UPDATE_TYPE = "heartbeat"
OPERATION = "hardware.soaibench.events.publish"


async def publish_soaibench_run_update(
    *,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    run: JSONDict,
    update_type: str,
    task_id: str | None = None,
) -> None:
    run_id = str(run["run_id"])
    try:
        event_run = dict(run)
        event_run["task_id"] = task_id
        await event_bus.publish(_event_from_run(run=event_run, update_type=update_type))
    except asyncio.CancelledError as exception:
        exception.add_note("SoAIBench realtime update publication was cancelled.")
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(exception, operation=OPERATION)
        if update_type == HEARTBEAT_UPDATE_TYPE:
            log_exception(
                logger,
                coerced_exception,
                message="SoAIBench realtime update publication failed.",
                operation=OPERATION,
                details={"run_id": run_id, "update_type": update_type},
                level="warning",
            )
            return
        raise coerced_exception from exception


async def publish_soaibench_worker_update(
    context: SoAIBenchWorkerEventContext,
    run: JSONDict,
    update_type: str,
) -> None:
    await publish_soaibench_run_update(
        event_bus=context.event_bus,
        logger=context.logger,
        run=run,
        update_type=update_type,
        task_id=context.task_id,
    )


def _event_from_run(*, run: JSONDict, update_type: str) -> SoAIBenchRunUpdatedEvent:
    delivery = (
        EventDelivery.DROPPABLE
        if update_type == HEARTBEAT_UPDATE_TYPE
        else EventDelivery.MUST_DELIVER
    )
    return SoAIBenchRunUpdatedEvent(
        user_id=require_int_from_numberish(run["created_by_user_id"], field="created_by_user_id"),
        device_id=str(run["device_id"]),
        run_id=str(run["run_id"]),
        update_seq=coerce_non_negative_exact_int_or_zero(run.get("update_seq")),
        update_type=update_type,
        run=run_response(run, accepted=run.get("status") == "running"),
        delivery=delivery,
    )
