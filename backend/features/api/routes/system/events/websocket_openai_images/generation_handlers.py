"""SoAI - WebSocket OpenAI images generation handlers [backend/features/api/routes/system/events/websocket_openai_images/generation_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import HTTPException

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.events.types_models_requests import ImageGenerationRequestReceived
from core.logging.trace import get_logger
from core.openai.inference_normalization import normalize_openai_inference_payload
from core.openai.request_fields import resolve_optional_model_name
from core.orchestrator.protocols_lifecycle import InferenceAdmissionRequest
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.runtime.soai_identifiers import create_system_id
from core.tasks.type_catalog import TASK_TYPE_IMAGE_GENERATION
from core.timing.monotonic import monotonic_ms
from core.types.json_value import coerce_json_dict
from core.users.user_id import coerce_user_id
from features.api.routes.openai.images_request_validation import (
    preprocess_openai_image_generation_request_json,
)
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_openai_images.generation_runner import (
    run_openai_images_generation,
)
from features.api.routes.system.events.websocket_openai_images.payloads import (
    build_openai_images_generation_error,
    build_openai_images_generation_started,
)
from features.api.routes.system.events.websocket_openai_run_start_guard import (
    guard_openai_ws_run_start,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    resolve_openai_ws_reply_queue_or_enqueue_unavailable,
)
from features.api.routes.system.events.websocket_run_payloads import require_run_id
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.inference_request_model_resolution import (
    resolve_effective_inference_model_resolution,
)
from features.api.schemas.openai_images import ImageGenerationRequest
from features.api.streaming.websocket_openai_runtime import OpenAiImageGenerationRuntime

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import InferenceDeliveryMode
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("handle_openai_images_generation_start",)

LOGGER_NAME = "SoAI.features.api.generation_handlers"
OPERATION_IMAGES_GENERATION_VALIDATE = "api_system.websocket.openai_images.generation.validate"


async def handle_openai_images_generation_start(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request_context: RequestContext,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    shutdown_event: asyncio.Event,
) -> None:
    logger = get_logger(LOGGER_NAME)

    run_id = await guard_openai_ws_run_start(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        error_event_type=WebSocketEventTypes.OPENAI_IMAGES_GENERATION_ERROR,
        build_forbidden_error_payload=build_openai_images_generation_error,
        warn_label="OpenAI images generation error",
        require_run_id=require_run_id,
    )
    if run_id is None:
        return
    runtimes = connection.openai_image_generations
    if run_id in runtimes:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_images_generation_error(
                run_id=run_id,
                message="Image generation run_id already exists.",
                code="conflict_error",
            ),
            "OpenAI images generation error",
        )
        return
    payload_value = coerce_json_dict(data.get("payload"))
    if payload_value is None:
        payload_value = data
    try:
        validated = ImageGenerationRequest.model_validate(payload_value)
    except ValueError as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_IMAGES_GENERATION_VALIDATE,
        )
        log_exception(
            logger,
            exception,
            message="Invalid OpenAI images generation request payload (non-critical).",
            operation=OPERATION_IMAGES_GENERATION_VALIDATE,
            trace_id=trace_id,
            level="debug",
        )
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_images_generation_error(
                run_id=run_id,
                message=str(coerced),
                code="invalid_request_error",
            ),
            "OpenAI images generation error",
        )
        return
    request_json = validated.model_dump(exclude_none=True, exclude_unset=True, by_alias=True)
    request_json = normalize_openai_inference_payload(
        request_json,
        logger=logger,
        trace_id=trace_id,
        filter_request_fields=False,
    ).payload
    try:
        await preprocess_openai_image_generation_request_json(api_context, request_json)
    except HTTPException as exception:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_images_generation_error(
                run_id=run_id,
                message=(str(exception.detail) if exception.detail else "Invalid request."),
                code="invalid_request_error",
            ),
            "OpenAI images generation error",
        )
        return
    resolved = resolve_effective_inference_model_resolution(
        request_json=request_json,
        request_context=request_context,
        prepared_agent_request=None,
        apply_to_request_json=True,
    )
    effective_request_json = resolved.request_json
    normalized_for_capabilities = normalize_openai_inference_payload(
        effective_request_json,
        logger=logger,
        trace_id=trace_id,
        base_capabilities=("images",),
        filter_request_fields=True,
    )
    capabilities = normalized_for_capabilities.required_capabilities
    modalities = normalized_for_capabilities.required_modalities
    stream_enabled = effective_request_json.get("stream") is True
    cancellation_id = create_system_id(
        subsystem="ws_openai_images",
        owner=run_id,
        include_random_suffix=True,
    )
    user_id = coerce_user_id(request_context.user_id)
    delivery_mode: InferenceDeliveryMode = "streaming" if stream_enabled else "blocking"
    receipt = await api_context.dependencies.orchestrator_control.accept_inference_request(
        InferenceAdmissionRequest(
            request_context=request_context,
            payload=effective_request_json,
            task_type=TASK_TYPE_IMAGE_GENERATION,
            user_id=user_id,
            owner_type="system",
            owner_id=run_id,
            cancellation_id=cancellation_id,
            metadata={"run_id": run_id, "openai_images_generation": True},
            request_event_class=ImageGenerationRequestReceived,
            required_capabilities=capabilities,
            required_modalities=modalities,
            request_source=REQUEST_SOURCE_WEBUI_WS,
            delivery_mode=delivery_mode,
            attach_reply_queue=True,
        ),
    )
    reply_queue = resolve_openai_ws_reply_queue_or_enqueue_unavailable(
        receipt=receipt,
        enqueue_warning_tracker=enqueue_warning_tracker,
        queue=connection.queue,
        warn_label="OpenAI images generation error",
        build_error_payload=build_openai_images_generation_error,
        run_id=run_id,
        message="Image generation reply channel is not available.",
    )
    if reply_queue is None:
        return
    task = receipt.task
    runtime = OpenAiImageGenerationRuntime(
        run_id=run_id,
        user_id=user_id,
        started_at_ms=monotonic_ms(),
        active_task_id=task.task_id,
        detach_event=asyncio.Event(),
        runner_task=None,
    )
    runtimes[run_id] = runtime
    model_id = resolve_optional_model_name(effective_request_json)
    runner_task = api_context.dependencies.application_control.schedule_background_task(
        run_openai_images_generation(
            run_id=run_id,
            runtime=runtime,
            runtimes=runtimes,
            connection=connection,
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            request_context=request_context,
            reply_queue=reply_queue,
            task_id=task.task_id,
            model_id=model_id,
            stream_enabled=stream_enabled,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            shutdown_event=shutdown_event,
        ),
        name=f"ws_openai_images_generation:{run_id}",
    )
    if runner_task is None:
        if runtimes.get(run_id) is runtime:
            runtimes.pop(run_id, None)
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_images_generation_error(
                run_id=run_id,
                message="Image generation runner could not be scheduled.",
                code="server_error",
                task_id=task.task_id,
            ),
            "OpenAI images generation error",
        )
        return
    runtime.runner_task = runner_task
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_openai_images_generation_started(
            run_id=run_id,
            task_id=task.task_id,
            stream=stream_enabled,
        ),
        "OpenAI images generation started",
    )
