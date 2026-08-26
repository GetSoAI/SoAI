"""SoAI - Durable admission for pre-created inference tasks [backend/orchestrator/control/inference_existing_task_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import replace

from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.bus_dispatch_logging import resolve_event_trace_id
from core.events.types_models_requests import InferenceRequestReceived
from core.licensing.admission import LicensingOperationClass
from core.licensing.enforcement import LICENSING_RESTRICTED_MESSAGE
from core.licensing.protocols import LicensingStatusProtocol
from core.logging.trace import get_logger
from core.openai.request_fields import require_model_name
from core.orchestrator.protocols_scheduler import SchedulerPlanningProtocol
from core.runtime.shutdown_errors import SERVER_SHUTTING_DOWN_MESSAGE
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.failure_events import send_error_event, send_error_event_and_finalize
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.orchestration_persistence import cache_and_persist_orchestration_state
from core.tasks.task_cancellation import cancel
from orchestrator.control.inference_request_primitives import (
    serialize_request_context_payload,
)
from orchestrator.durable_requeue import durably_requeue_task
from orchestrator.queueing.execution_plan_context import (
    apply_execution_plan_context,
    resolve_execution_plan_routing_key,
)
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("admit_existing_inference_task_event",)

LOGGER_NAME = "SoAI.orchestrator.control.inference_existing_task_admission"
OPERATION = "orchestrator.control.inference_existing.plan"
OPERATION_PERSIST_CONTEXT = "orchestrator.control.inference_existing.persist_context"
OPERATION_REQUEUE_TASK = "orchestrator.control.inference_existing.requeue"


async def admit_existing_inference_task_event(
    *,
    queue: QueueServiceView,
    planner: SchedulerPlanningProtocol,
    licensing_status: LicensingStatusProtocol,
    event: InferenceRequestReceived,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if queue.is_quiescent.is_set():
        await send_error_event(
            event.reply_channel,
            SERVER_SHUTTING_DOWN_MESSAGE,
            ErrorType.SERVICE_UNAVAILABLE,
            context=event.context,
        )
        if isinstance(event.task_id, str) and event.task_id.strip():
            await cancel(
                queue.task_registry,
                event.task_id,
                reason=SERVER_SHUTTING_DOWN_MESSAGE,
                context=event.context,
            )
        return
    task_id = event.task_id
    if not isinstance(task_id, str) or not task_id.strip():
        await send_error_event(
            event.reply_channel,
            "Task ID is required.",
            ErrorType.INVALID_REQUEST,
            context=event.context,
        )
        return
    registry = queue.task_registry
    task = await registry.attach_reply_queue(task_id, event.reply_channel)
    if task is None:
        await send_error_event(
            event.reply_channel,
            "Task not found.",
            ErrorType.INVALID_REQUEST,
            context=event.context,
        )
        return
    if task.status.is_terminal():
        await send_error_event(
            event.reply_channel,
            "Task is already terminal.",
            ErrorType.INVALID_REQUEST,
            context=event.context,
        )
        return
    licensing_admission = await licensing_status.admission(LicensingOperationClass.ORDINARY)
    if not licensing_admission.allowed:
        await send_error_event_and_finalize(
            event.reply_channel,
            LICENSING_RESTRICTED_MESSAGE,
            ErrorType.FORBIDDEN,
            registry=registry,
            task_id=task_id,
        )
        return
    cancel_decision = await queue.cancel_if_cancelled(
        task,
        reason="Task cancelled before processing.",
    )
    if cancel_decision is not None:
        return
    try:
        model_name = require_model_name(event.payload)
    except ValidationError as exception:
        await send_error_event_and_finalize(
            event.reply_channel,
            str(exception) or "Request validation failed.",
            ErrorType.INVALID_REQUEST,
            registry=registry,
            task_id=task_id,
        )
        return
    context = task.orchestration_context or OrchestrationContext()
    request_source_value = context.request_source
    if request_source_value is None:
        await send_error_event_and_finalize(
            event.reply_channel,
            "Task orchestration context is missing request_source.",
            ErrorType.SERVER_ERROR,
            registry=registry,
            task_id=task_id,
        )
        return
    delivery_mode_value = context.delivery_mode
    delivery_mode = delivery_mode_value.strip() if isinstance(delivery_mode_value, str) else ""
    if not delivery_mode:
        await send_error_event_and_finalize(
            event.reply_channel,
            "Task orchestration context is missing delivery_mode.",
            ErrorType.SERVER_ERROR,
            registry=registry,
            task_id=task_id,
        )
        return
    request_context = replace(
        context,
        priority_assignment=await queue.assign_request_priority(event.payload),
        event=event,
        request_payload=dict(event.payload),
        request_event_type=event.__class__.__name__,
        request_context_data=serialize_request_context_payload(event.context),
        required_capabilities=tuple(event.required_capabilities or ()),
        required_modalities=tuple(event.required_modalities or ()),
        request_source=request_source_value,
        delivery_mode=delivery_mode,
    )
    reservation_committed = False
    try:
        try:
            plan = await planner.resolve_execution_plan(
                task,
                request_context,
                set(context.excluded_universal_ids) if context.excluded_universal_ids else None,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to resolve execution plan for pre-created task admission.",
                operation=OPERATION,
                details={"task_id": task_id},
                level="warning",
            )
            await queue.execution_reservations.release(request_context.tracking_id)
            await send_error_event_and_finalize(
                event.reply_channel,
                "Failed to plan request.",
                ErrorType.SERVER_ERROR,
                registry=registry,
                task_id=task_id,
            )
            return
        if plan["status"] == "UNAVAILABLE":
            failure_error_type = plan.get("failure_error_type")
            failure_reason = plan.get("failure_reason")
            if (
                failure_error_type == "invalid_request"
                and isinstance(failure_reason, str)
                and failure_reason
            ):
                await queue.execution_reservations.release(request_context.tracking_id)
                await send_error_event_and_finalize(
                    event.reply_channel,
                    failure_reason,
                    ErrorType.INVALID_REQUEST,
                    registry=registry,
                    task_id=task_id,
                )
                return
        routing_key = resolve_execution_plan_routing_key(
            request_context,
            plan,
            requested_model_name=model_name,
        )
        plan_context = await apply_execution_plan_context(
            queue=queue,
            task=task,
            context=request_context,
            plan=plan,
            routing_key=routing_key,
        )
        task = plan_context.task
        persisted, _ = await cache_and_persist_orchestration_state(
            registry,
            task,
            logger=logger,
            operation=OPERATION_PERSIST_CONTEXT,
            trace_id=resolve_event_trace_id(event),
        )
        if not persisted:
            await queue.execution_reservations.release(request_context.tracking_id)
            await send_error_event_and_finalize(
                event.reply_channel,
                TASK_STATE_PERSISTENCE_FAILED_MESSAGE,
                ErrorType.SERVER_ERROR,
                registry=registry,
                task_id=task_id,
            )
            return
        requeued = await durably_requeue_task(
            queue,
            registry,
            task,
            logger=logger,
            operation=OPERATION_REQUEUE_TASK,
            failure_message="Failed to enqueue pre-created task for orchestration.",
        )
        if not requeued:
            await queue.execution_reservations.release(request_context.tracking_id)
            await send_error_event_and_finalize(
                event.reply_channel,
                "Failed to enqueue task for orchestration.",
                ErrorType.SERVER_ERROR,
                registry=registry,
                task_id=task_id,
            )
            return
        reservation_committed = True
    except asyncio.CancelledError:
        if not reservation_committed:
            await queue.execution_reservations.release(request_context.tracking_id)
        raise
    except Exception as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Failed to admit pre-created inference task.",
            operation=OPERATION,
            details={"task_id": task_id},
        )
        if not reservation_committed:
            await queue.execution_reservations.release(request_context.tracking_id)
        raise
    refreshed = await registry.get(task.task_id, force_refresh=True)
    if refreshed is not None:
        await registry.update_task_cache(refreshed)
