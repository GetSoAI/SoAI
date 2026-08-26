"""SoAI - Task cancellation coordination and event publication [backend/core/tasks/cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.context import require_context_cancellation_id
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_tasks import CancelTaskCommand
from core.logging.trace import get_logger
from core.runtime.protocols import RequestContextProtocol
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
)

__all__ = ("publish_cancel",)

LOGGER_NAME = "SoAI.core.tasks.cancellation"
OPERATION_TASK_CANCELLATION_PUBLISH_CANCEL = "task_cancellation.publish_cancel"
OPERATION_TASK_CANCELLATION_PUBLISH_CANCEL_SHOULD_PUBLISH_CANCEL_COMMAND = (
    "task_cancellation.publish_cancel.should_publish_cancel_command"
)


async def publish_cancel(
    event_bus: EventBusProtocol,
    cancellation_coordinator: CancellationCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol,
    context: RequestContextProtocol | None,
    reason: str,
    *,
    cancellation_id: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if cancellation_coordinator is None:
        raise StateError("Cancellation coordinator is required.")
    if cancellation_history is None:
        raise StateError("Cancellation history is required.")
    if event_bus is None:
        raise StateError("Event bus is required.")
    resolved = (
        cancellation_id if cancellation_id is not None else require_context_cancellation_id(context)
    )
    normalized_id = require_cancellation_id(resolved)
    normalized_reason = str(reason or "").strip() or "Cancelled"
    newly_cancelled = False
    try:
        newly_cancelled = await cancellation_coordinator.cancel_scope(
            normalized_id,
            normalized_reason,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to cancel via CancellationRegistry",
            operation=OPERATION_TASK_CANCELLATION_PUBLISH_CANCEL,
            details={"cancellation_id": normalized_id},
        )
        return
    if not newly_cancelled:
        try:
            should_publish = await cancellation_history.check_publish_rate_limit(
                normalized_id,
                min_interval=1.0,
            )
            if not should_publish:
                return
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Cancellation publish decision failed (non-critical).",
                operation=OPERATION_TASK_CANCELLATION_PUBLISH_CANCEL_SHOULD_PUBLISH_CANCEL_COMMAND,
                details={"cancellation_id": normalized_id},
                level="debug",
            )
            return
    publish_reason = reason if str(reason or "").strip() else normalized_reason
    try:
        await event_bus.publish(
            CancelTaskCommand(
                cancellation_id=normalized_id, reason=publish_reason, context=context
            ),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to publish CancelTaskCommand",
            operation=OPERATION_TASK_CANCELLATION_PUBLISH_CANCEL,
            details={"cancellation_id": normalized_id},
        )
