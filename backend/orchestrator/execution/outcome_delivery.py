"""SoAI - Delivery helpers for task outcome finalization [backend/orchestrator/execution/outcome_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.reply_queue_terminal_delivery import (
    try_deliver_terminal_reply_event,
)
from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_status_error
from core.errors.status_mapping import error_type_to_status_code
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC
from orchestrator.execution.event_context import is_streaming_request
from orchestrator.execution.internal_protocols import DeliveryManagerProtocol
from orchestrator.queueing.internal_protocols import QueueServiceView

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "prepare_failure_delivery",
    "try_publish_error_event",
)

OPERATION_ORCHESTRATOR_EXECUTION_OUTCOME_DELIVERY_TRY_PUBLISH_ERROR_EVENT = (
    "orchestrator.outcome_delivery.error_event"
)


LOGGER_NAME = "SoAI.orchestrator.execution.outcome_delivery"


async def prepare_failure_delivery(
    queue: QueueServiceView,
    delivery: DeliveryManagerProtocol,
    task: Task,
    *,
    reason: str,
) -> tuple[OrchestrationContext, Task, int | None, str | None, BaseException | None]:
    context = queue.require_orchestration_context(task)
    dedup_exception: BaseException | None = None
    dedup_hash_to_notify: str | None = None
    task, delivery_version = await delivery.prepare_delivery(task)
    if delivery_version is None:
        return (context, task, None, None, None)
    context = queue.require_orchestration_context(task)
    if context.dedup_hash and task.status != TaskStatus.DEDUPED:
        dedup_hash_to_notify = context.dedup_hash
        dedup_exception = RuntimeError(reason)
    return (context, task, delivery_version, dedup_hash_to_notify, dedup_exception)


async def try_publish_error_event(
    delivery: DeliveryManagerProtocol,
    task: Task,
    *,
    context: OrchestrationContext,
    reason: str,
    error_type: ErrorType,
    log_message: str,
    operation: str,
    reason_is_public: bool = False,
    details: JSONDict | None = None,
    level: str | None = None,
) -> bool:
    _ = delivery
    logger = get_logger(LOGGER_NAME)
    try:
        reply_queue = task.reply_queue
        if reply_queue is None:
            return True
        event = context.event
        event_context = event.context if event else None
        public_message = reason
        if task.status != TaskStatus.CANCELLED and not reason_is_public:
            public_error = project_public_status_error(
                status_code=error_type_to_status_code(error_type),
                code=error_type.value,
                message=reason,
            )
            public_message = public_error.message
        terminal_event: Event
        if task.status == TaskStatus.CANCELLED:
            terminal_event = TaskCompleteEvent(
                success=False,
                message="Request cancelled.",
                task_id=task.task_id,
                user_id=task.user_id,
                status=TaskStatus.CANCELLED.value,
            )
        else:
            terminal_event = ErrorEvent(
                message=public_message,
                error_type=error_type,
                context=event_context,
                trace_id=(
                    event.trace_id
                    or (event_context.trace_id if event_context is not None else None)
                    if event is not None
                    else None
                ),
            )
        return await try_deliver_terminal_reply_event(
            reply_queue=reply_queue,
            event=terminal_event,
            timeout_seconds=(
                LOCAL_IO_TIMEOUT_SEC if is_streaming_request(context) else RESPONSIVE_TIMEOUT_SEC
            ),
            logger=logger,
            operation=operation,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        resolved_details: JSONDict = {}
        if details:
            resolved_details.update(dict(details))
        resolved_details["operation"] = operation
        resolved_details["log_message"] = log_message
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_ORCHESTRATOR_EXECUTION_OUTCOME_DELIVERY_TRY_PUBLISH_ERROR_EVENT,
        )
        log_exception(
            logger,
            coerced,
            message="Terminal reply event delivery failed.",
            operation=OPERATION_ORCHESTRATOR_EXECUTION_OUTCOME_DELIVERY_TRY_PUBLISH_ERROR_EVENT,
            details=resolved_details or None,
            level=level or "warning",
        )
        return False
