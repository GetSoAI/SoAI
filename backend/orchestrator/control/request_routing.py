"""SoAI - Orchestrator request routing and queue decision handling [backend/orchestrator/control/request_routing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from core.di.validation import require_dependencies
from core.errors.error_types import ErrorType
from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
    ImageEditRequestReceived,
    ImageVariationRequestReceived,
    InferenceRequestReceived,
)
from core.licensing.protocols import LicensingStatusProtocol
from core.logging.trace import get_logger
from core.orchestrator.protocols_scheduler import (
    OrchestratorSchedulerProtocol,
    SchedulerPlanningProtocol,
)
from core.orchestrator.queue_decisions import QueueDecision, QueueDecisionType
from orchestrator.control.inference_existing_task_admission import (
    admit_existing_inference_task_event,
)
from orchestrator.internal_protocols import (
    OrchestratorHandlersProtocol,
    OrchestratorTaskOutcomesProtocol,
)
from orchestrator.queueing.execution_plan_error_handling import (
    run_execution_plan_with_reservation_guard,
)
from orchestrator.queueing.execution_plans import apply_execution_plan
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = (
    "OrchestratorRequestRoutingDependencies",
    "handle_inference_request",
    "handle_media_or_vision_request",
    "handle_queue_decision",
)

_HANDLE_QUEUE_DECISION_OPERATION = "orchestrator.handle_queue_decision"
LOGGER_NAME = "SoAI.orchestrator.control.request_routing"


@dataclass(frozen=True, slots=True)
class OrchestratorRequestRoutingDependencies:
    queue: QueueServiceView
    scheduler: OrchestratorSchedulerProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    handlers: OrchestratorHandlersProtocol
    planner: SchedulerPlanningProtocol
    licensing_status: LicensingStatusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorRequestRoutingDependencies",
            handlers=self.handlers,
            licensing_status=self.licensing_status,
            outcomes=self.outcomes,
            planner=self.planner,
            queue=self.queue,
            scheduler=self.scheduler,
        )


async def handle_queue_decision(
    deps: OrchestratorRequestRoutingDependencies,
    decision: QueueDecision,
) -> None:
    if decision.decision_type == QueueDecisionType.PLAN_REQUIRED:
        task = decision.task
        if task is None:
            _raise_queue_decision_state_error(
                "Plan-required queue decision missing task.",
                decision,
            )
        context = deps.queue.require_orchestration_context(task)
        event = context.event
        if event is None:
            await deps.outcomes.fail_task(
                task=task,
                reason="Missing inference event for task.",
                allow_failover=False,
            )
            return
        plan = await deps.planner.resolve_execution_plan(
            task,
            context,
            set(context.excluded_universal_ids) if context.excluded_universal_ids else None,
        )
        followup = await run_execution_plan_with_reservation_guard(
            reservations=deps.queue.execution_reservations,
            tracking_id=context.tracking_id,
            awaitable=apply_execution_plan(queue=deps.queue, task=task, plan=plan),
            logger=get_logger(LOGGER_NAME),
            operation=_HANDLE_QUEUE_DECISION_OPERATION,
            message="Failed to apply execution plan for queue decision.",
            details={"tracking_id": context.tracking_id},
        )
        for next_decision in followup:
            await handle_queue_decision(deps, decision=next_decision)
        return
    if decision.decision_type == QueueDecisionType.DISPATCH_CANDIDATE:
        task = decision.task
        if task is None:
            _raise_queue_decision_state_error(
                "Dispatch-candidate queue decision missing task.",
                decision,
            )
        if decision.model_info is None:
            _raise_queue_decision_state_error(
                "Dispatch-candidate queue decision missing model info.",
                decision,
            )
        model_info = decision.model_info
        plugin_name = decision.plugin_name
        if not plugin_name:
            _raise_queue_decision_state_error(
                "Dispatch-candidate queue decision missing plugin name.",
                decision,
            )
        routing_key = decision.routing_key
        if not routing_key:
            _raise_queue_decision_state_error(
                "Dispatch-candidate queue decision missing routing key.",
                decision,
            )
        await deps.scheduler.handle_dispatch_candidate(
            task=task,
            model_info=model_info,
            plugin_name=plugin_name,
            routing_key=routing_key,
            from_queue=decision.from_queue,
        )
        return
    if decision.decision_type in {QueueDecisionType.FAIL_TASK, QueueDecisionType.CANCEL_TASK}:
        task = decision.task
        if task is None:
            _raise_queue_decision_state_error("Terminal queue decision missing task.", decision)
        reason = decision.reason
        if not reason:
            _raise_queue_decision_state_error("Terminal queue decision missing reason.", decision)
        error_type = decision.error_type or ErrorType.SERVER_ERROR
        if decision.decision_type == QueueDecisionType.FAIL_TASK:
            await deps.outcomes.fail_task(
                task=task,
                reason=reason,
                allow_failover=decision.allow_failover,
                error_type=error_type,
            )
        else:
            await deps.outcomes.cancel_task(
                task=task,
                reason=reason,
                error_type=error_type,
            )
        return
    if decision.decision_type == QueueDecisionType.SCHEDULE_WORK:
        work_item = decision.work_item
        if work_item is None:
            _raise_queue_decision_state_error(
                "Schedule-work queue decision missing work item.",
                decision,
            )
        await deps.scheduler.queue_scheduler_work(work_item=work_item)
        return
    _raise_queue_decision_state_error("Unhandled queue decision type.", decision)


def _raise_queue_decision_state_error(message: str, decision: QueueDecision) -> NoReturn:
    raise StateError(
        message,
        operation=_HANDLE_QUEUE_DECISION_OPERATION,
        details={"decision_type": decision.decision_type.value},
    )


async def handle_inference_request(
    event: Event,
    *,
    deps: OrchestratorRequestRoutingDependencies,
) -> None:
    if not isinstance(event, InferenceRequestReceived):
        return
    await admit_existing_inference_task_event(
        queue=deps.queue,
        planner=deps.planner,
        licensing_status=deps.licensing_status,
        event=event,
    )


async def handle_media_or_vision_request(
    event: Event,
    *,
    deps: OrchestratorRequestRoutingDependencies,
) -> None:
    if isinstance(event, AudioTranscriptionRequestReceived):
        bridge = await deps.handlers.handle_audio_transcription_request(event)
    elif isinstance(event, AudioTranslationRequestReceived):
        bridge = await deps.handlers.handle_audio_translation_request(event)
    elif isinstance(event, ImageEditRequestReceived):
        bridge = await deps.handlers.handle_image_edit_request(event)
    elif isinstance(event, ImageVariationRequestReceived):
        bridge = await deps.handlers.handle_image_variation_request(event)
    else:
        return
    if bridge:
        await handle_inference_request(bridge, deps=deps)
