"""SoAI - Plugin slot inference dispatch and requeue handling [backend/orchestrator/execution/plugin_slot_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_float
from core.errors.error_types import ErrorType
from core.errors.exceptions import ModelOutputContractError, ValidationError
from core.events.publication_errors import PublicationDeadlineExceededError
from core.events.types_models_requests import (
    EmbeddingRequestReceived,
    InferenceRequestReceived,
)
from core.logging.protocols import TraceLogger
from core.metrics.protocols import MetricsManagerProtocol
from core.openai.request_features import (
    coerce_stream_requested,
    extract_usage_reporting_requested,
)
from core.openai.request_requirement_failures import (
    build_openai_request_requirement_failure_message,
    classify_openai_request_requirement_mismatch,
)
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.protocols import StateAggregatorProtocol
from core.state.state_names import ORCH_STATE_PROCESSING
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.streaming_prefill_timeout import resolve_streaming_first_chunk_timeout
from core.tasks.task import Task
from core.tasks.type_catalog import TASK_TYPE_TEXT_TO_SPEECH
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from orchestrator.execution.internal_protocols import (
    ActiveInferenceRegistryProtocol,
    InferencePayloadPreparerProtocol,
    OutcomeManagerProtocol,
    ResultProcessorProtocol,
)
from orchestrator.execution.plugin_slot_inference import (
    execute_plugin_inference_request,
)
from orchestrator.execution.requeue import RequeueTask
from orchestrator.execution.result_handlers import handle_unary_result
from orchestrator.execution.retry_policy import resolve_max_execution_attempts
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)
from orchestrator.lifecycle.task_tracking.model_context import build_model_context
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.scheduling.plugin_dispatch_readiness import (
    requeue_deferred_plugin_dispatch,
)
from orchestrator.scheduling.plugin_warning_throttles import (
    format_suppressed_warning_suffix,
    get_plugin_warning_throttle,
)

if TYPE_CHECKING:
    from core.logging.rate_limited_logger import RateLimitedLogger
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecyclePublisherProtocol
    from core.types.json import JSONDict, JSONValue
    from orchestrator.execution.chat_template_role_policy import (
        ChatTemplateRolePolicyResolver,
    )
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )

__all__ = ("execute_task_within_plugin_slot",)


async def _ensure_processing_state_for_inference(
    *,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    warning_throttles: dict[str, RateLimitedLogger],
    plugin_name: str,
    task_id: str,
    universal_id: JSONValue,
    logger: TraceLogger,
) -> None:
    current_plugin_status = await state_aggregator.get_plugin_status(plugin_name)
    if current_plugin_status == ORCH_STATE_PROCESSING:
        return
    try:
        await publish_runtime_state_change_and_wait(
            publisher=publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_PROCESSING,
            reason=f"Processing task {task_id}",
            details={"universal_id": universal_id},
        )
    except PublicationDeadlineExceededError:
        authoritative_status = await state_aggregator.get_plugin_status(plugin_name)
        if authoritative_status != ORCH_STATE_PROCESSING:
            raise
        warning_throttle = get_plugin_warning_throttle(
            warning_throttles,
            f"processing-publication:{plugin_name}",
            interval_seconds=INTERACTIVE_TIMEOUT_SEC,
        )
        should_emit, suppressed = warning_throttle.should_emit()
        if should_emit:
            logger.warning(
                "Continuing task %s on plugin '%s' after the PROCESSING publication receipt timed out; authoritative state is PROCESSING.%s",
                task_id,
                plugin_name,
                format_suppressed_warning_suffix(suppressed),
            )


def prepare_inference_payload(
    prepared_payload: JSONDict,
    *,
    request_timeout: float,
    raw_timeout: JSONValue,
    logger: TraceLogger,
) -> tuple[JSONDict, float]:
    next_request_timeout = request_timeout
    if (
        isinstance(raw_timeout, int | float)
        and (not isinstance(raw_timeout, bool))
        and float(raw_timeout) > 0
    ):
        coerced_timeout = coerce_positive_float(
            raw_timeout,
            default=request_timeout,
            label="request.timeout",
            logger=logger,
        )
        next_request_timeout = min(request_timeout, coerced_timeout)
    messages_value = prepared_payload.get("messages")
    normalized_payload = prepared_payload
    if isinstance(messages_value, list) and not prepared_payload.get("stream", False):
        normalized_payload = dict(prepared_payload)
        normalized_payload["stream"] = True
        stream_options = prepared_payload.get("stream_options")
        normalized_payload["stream_options"] = {
            **(stream_options if isinstance(stream_options, dict) else {}),
            "include_usage": True,
        }
    return (normalized_payload, next_request_timeout)


async def execute_task_within_plugin_slot(
    queue: QueueServiceView,
    task_registry: TaskRegistryProtocol,
    state_aggregator: StateAggregatorProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    payload_preparer: InferencePayloadPreparerProtocol,
    results: ResultProcessorProtocol,
    outcomes: OutcomeManagerProtocol,
    metrics: MetricsManagerProtocol,
    role_policy_resolver: ChatTemplateRolePolicyResolver,
    *,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    requeue_inside_slot_warners: dict[str, RateLimitedLogger],
    admission_registered: bool,
    task: Task,
    plugin_instance: PluginInstanceProtocol,
    plugin_name: str,
    tracking_id: str,
    request_timeout: float,
    health_check_config: JSONDict,
    model_info: JSONDict,
    event: InferenceRequestReceived,
    logger: TraceLogger,
) -> tuple[Task, bool]:
    if not admission_registered:
        current_plugin_status = await state_aggregator.get_plugin_status(plugin_name)
        requeue_result = await requeue_deferred_plugin_dispatch(
            queue=queue,
            task_registry=task_registry,
            outcomes=outcomes,
            task=task,
            logger=logger,
            operation="orchestrator.execution.requeue_inside_plugin_slot",
            warning_message=(
                "Task %s dispatch aborted inside its plugin slot. "
                "Plugin '%s' state is now '%s'. Re-queuing.%s"
            ),
            warning_args=(task.task_id, plugin_name, current_plugin_status),
            warner=get_plugin_warning_throttle(
                requeue_inside_slot_warners,
                plugin_name,
                interval_seconds=INTERACTIVE_TIMEOUT_SEC,
            ),
        )
        task = requeue_result.task
        if requeue_result.requeued:
            raise RequeueTask()
        return (task, False)
    await _ensure_processing_state_for_inference(
        publisher=lifecycle.publisher,
        state_aggregator=state_aggregator,
        warning_throttles=requeue_inside_slot_warners,
        plugin_name=plugin_name,
        task_id=task.task_id,
        universal_id=model_info.get("universal_id"),
        logger=logger,
    )
    await active_inferences.set_dispatch_time(tracking_id, time.monotonic())
    logger.trace(
        "Task %s acquired concurrency slot on plugin '%s'.",
        task.task_id,
        plugin_name,
    )
    model_context = build_model_context(task, model_info)
    if isinstance(event, EmbeddingRequestReceived):
        embedding_result = await asyncio.wait_for(
            plugin_instance.handle_embedding_request(
                event.payload,
                event.context,
                model_context,
            ),
            timeout=request_timeout,
        )
        unary_result = handle_unary_result(
            results,
            task,
            model_info,
            embedding_result,
            plugin_name=plugin_name,
        )
        await outcomes.succeed_task(task, result=unary_result)
        return (task, True)
    try:
        prepared_payload = await payload_preparer.prepare_inference_payload_for_plugin(
            task,
            plugin_name,
            model_info,
        )
    except ValidationError as exception:
        mismatch = classify_openai_request_requirement_mismatch(
            message=str(exception),
            details=exception.details,
        )
        await outcomes.fail_task(
            task,
            (
                build_openai_request_requirement_failure_message(mismatch)
                if mismatch is not None
                else str(exception)
            ),
            allow_failover=False,
            error_type=ErrorType.INVALID_REQUEST,
        )
        return (task, False)
    raw_timeout = event.payload.get("timeout")
    prepared_payload, request_timeout = prepare_inference_payload(
        prepared_payload,
        request_timeout=request_timeout,
        raw_timeout=raw_timeout,
        logger=logger,
    )
    requested_stream = coerce_stream_requested(
        event.payload,
        logger=logger,
        operation="orchestrator.execution.engine.coerce_payload_bool",
        default=False,
    )
    first_chunk_timeout = resolve_streaming_first_chunk_timeout(
        task=task,
        health_check_config=health_check_config,
    )
    tracking_timeout = (
        first_chunk_timeout if prepared_payload.get("stream") is True else request_timeout
    )
    await active_inferences.set_request_timeout(tracking_id, tracking_timeout)
    delivery_to_user = requested_stream or task.task_type == TASK_TYPE_TEXT_TO_SPEECH
    try:
        await execute_plugin_inference_request(
            results,
            outcomes,
            metrics=metrics,
            task_registry=task_registry,
            task=task,
            plugin_instance=plugin_instance,
            prepared_payload=prepared_payload,
            model_context=model_context,
            request_timeout=request_timeout,
            first_chunk_timeout=first_chunk_timeout,
            event=event,
            logger=logger,
            delivery_to_user=delivery_to_user,
            max_execution_retries=resolve_max_execution_attempts(),
            model_info=model_info,
            usage_reporting_requested=extract_usage_reporting_requested(event.payload),
            plugin_name=plugin_name,
            role_policy_resolver=role_policy_resolver,
        )
    except ModelOutputContractError as exception:
        await outcomes.fail_task(
            task,
            exception.message,
            allow_failover=False,
            error_type=ErrorType.MODEL_OUTPUT_CONTRACT,
        )
        return (task, False)
    return (task, True)
