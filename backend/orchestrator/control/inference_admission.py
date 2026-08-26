"""SoAI - Durable inference admission helpers [backend/orchestrator/control/inference_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.licensing.enforcement import require_ordinary_licensing
from core.logging.trace import get_logger
from core.openai.chat_messages_contracts import (
    validate_internal_chat_messages_contracts_for_sources,
)
from core.openai.request_fields import require_model_name
from core.openai.request_requirement_failures import (
    build_openai_request_requirement_failure_details,
    classify_openai_request_requirement_mismatch,
)
from core.orchestrator.protocols_lifecycle import (
    InferenceAdmissionReceipt,
    InferenceAdmissionRequest,
)
from core.runtime.shutdown_errors import SERVER_SHUTTING_DOWN_MESSAGE, ServerShuttingDownError
from core.tasks.enums import TaskStatus
from core.tasks.notifications import publish_event
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from core.timing.durations import days_to_ms
from orchestrator.control.inference_admission_persistence import (
    build_task_created_event,
    persist_admission,
    run_admission_side_effects,
)
from orchestrator.control.inference_admission_primitives import (
    build_inference_event,
    build_inference_task_request_context,
    resolve_reply_queue,
    serialize_request_context,
    validate_model_reference,
)
from orchestrator.execution.event_context import is_streaming_request
from orchestrator.queueing.execution_plan_context import (
    apply_execution_plan_context,
    resolve_execution_plan_routing_key,
)

if TYPE_CHECKING:
    from orchestrator.control.internal_protocols import (
        OrchestratorControlInferenceAdmissionProtocol,
    )

__all__ = ("accept_inference_request",)

LOGGER_NAME = "SoAI.orchestrator.control.inference_admission"
OPERATION_ACCEPT_INFERENCE_REQUEST = "orchestrator.control.inference_admission.accept"


async def accept_inference_request(
    control: OrchestratorControlInferenceAdmissionProtocol,
    request: InferenceAdmissionRequest,
) -> InferenceAdmissionReceipt:
    if control.is_quiescent():
        raise ServerShuttingDownError(SERVER_SHUTTING_DOWN_MESSAGE)
    await require_ordinary_licensing(control.deps.licensing_status)
    validate_internal_chat_messages_contracts_for_sources(
        request.payload,
        request_source=request.request_source,
    )
    model_name = require_model_name(request.payload)
    virtual_model_names, resolved_universal_id = await validate_model_reference(control, model_name)
    reply_queue = resolve_reply_queue(request)
    retention_days = control.queue.routing_config.inference_task_retention_days
    ttl_ms = None if retention_days <= 0 else days_to_ms(retention_days)
    task = Task.create(
        task_type=request.task_type,
        user_id=request.user_id,
        owner_id=request.owner_id,
        owner_type=request.owner_type,
        task_id=request.task_id,
        cancellation_id=request.cancellation_id,
        status=TaskStatus.QUEUED,
        ttl_ms=ttl_ms,
        metadata=request.metadata,
        reply_queue=reply_queue,
    )
    task_context = build_inference_task_request_context(
        inbound=request.request_context,
        task_id=task.task_id,
        cancellation_id=request.cancellation_id,
        user_id=request.user_id,
    )
    event = build_inference_event(
        request=request,
        request_context=task_context,
        task_id=task.task_id,
        reply_queue=reply_queue,
    )
    priority_assignment = await control.queue.assign_request_priority(request.payload)
    context = OrchestrationContext(
        priority_assignment=priority_assignment,
        event=event,
        routing_key=model_name if model_name in virtual_model_names else resolved_universal_id,
        request_payload=dict(request.payload),
        request_event_type=request.request_event_class.__name__,
        request_context_data=serialize_request_context(task_context),
        required_capabilities=tuple(request.required_capabilities),
        required_modalities=tuple(request.required_modalities),
        request_source=request.request_source,
        delivery_mode=request.delivery_mode,
    )
    persisted = False
    try:
        context = await _enrich_orchestration_context(
            control=control,
            task=task,
            context=context,
        )
        task = task.with_orchestration_context(context)
        await persist_admission(control, task)
        persisted = True
        await run_admission_side_effects(control, task, reply_queue)
        created_event = build_task_created_event(task)
        await publish_event(
            control.task_registry.event_bus,
            created_event,
            "TaskCreatedEvent",
        )
        control.queue.notify_durable_queue_wakeup()
    except asyncio.CancelledError:
        if not persisted:
            await control.queue.execution_reservations.release(context.tracking_id)
        raise
    except Exception as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_ACCEPT_INFERENCE_REQUEST,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to accept inference request.",
            operation=OPERATION_ACCEPT_INFERENCE_REQUEST,
            details={"tracking_id": context.tracking_id},
        )
        if not persisted:
            await control.queue.execution_reservations.release(context.tracking_id)
        raise
    return InferenceAdmissionReceipt(task=task, reply_queue=reply_queue)


async def _enrich_orchestration_context(
    *,
    control: OrchestratorControlInferenceAdmissionProtocol,
    task: Task,
    context: OrchestrationContext,
) -> OrchestrationContext:
    event = context.event
    if event is None:
        return context
    plan = await control.scheduler.planner.resolve_execution_plan(task, context, None)
    if plan["status"] == "UNAVAILABLE" and plan.get("failure_error_type") == "invalid_request":
        failure_reason = plan.get("failure_reason")
        if isinstance(failure_reason, str) and failure_reason:
            mismatch = classify_openai_request_requirement_mismatch(message=failure_reason)
            if mismatch is not None:
                raise ValidationError(
                    failure_reason,
                    details={
                        **build_openai_request_requirement_failure_details(mismatch),
                        "param": "model",
                    },
                )
            raise ValidationError(failure_reason, details={"param": "model"})
    plan_context = await apply_execution_plan_context(
        queue=control.queue,
        task=task,
        context=context,
        plan=plan,
        routing_key=resolve_execution_plan_routing_key(
            context,
            plan,
            requested_model_name=str(context.routing_key or ""),
        ),
    )
    enriched = plan_context.context
    if not enriched.execution_universal_ids:
        return enriched
    if control.queue.deduplication.enabled and (not is_streaming_request(enriched)):
        dedup_hash = control.queue.deduplication.calculate_dedup_hash(
            enriched,
            routing_config=control.queue.routing_config,
        )
        enriched = replace(enriched, dedup_hash=dedup_hash)
    return enriched
