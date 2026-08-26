"""SoAI - WebSocket model test stream runner [backend/features/api/routes/system/events/websocket_model_test_stream/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError
from core.logging.trace import get_logger
from core.openai.openai_error_objects import parse_openai_sse_error_frame
from core.openai.openai_sse_error_escalation import raise_openai_streaming_error
from core.openai.request_fields import resolve_optional_model_name
from core.openai.sse_chunk_decoding import decode_sse_chunk_bytes
from core.openai.stream_frame_processing import process_openai_stream_frame
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_sources import REQUEST_SOURCE_MODEL_TEST
from core.runtime.soai_identifiers import create_system_id, extend_soai_id
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.streaming_inference_admission import (
    create_streaming_inference_task,
)
from features.api.routes.system.events.websocket_model_test_stream.completion_events import (
    publish_model_test_stream_completion,
)
from features.api.routes.system.events.websocket_model_test_stream.failure_events import (
    publish_model_test_stream_error,
)
from features.api.routes.system.events.websocket_model_test_stream.state import (
    ModelTestStreamRuntime,
    publish_model_test_stream_event,
)
from features.api.routes.system.events.websocket_model_test_stream.task_error_detection import (
    raise_terminal_model_test_task_error,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    openai_ws_detach_event_is_set,
)
from features.api.streaming.openai_stream_generator.generator import (
    create_stream_generator,
)
from features.api.streaming.stream_cancel import schedule_streaming_task_cancel
from features.api.streaming.task_quota_metadata import (
    resolve_request_max_completion_tokens,
)
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "run_ws_model_test_stream",
    "schedule_ws_model_test_stream_cancel",
)

LOGGER_NAME = "SoAI.features.api.websocket_model_test_stream_runner"
OPERATION = "model_test_stream.run"


def _resolve_model_test_cancellation_id(
    *,
    runtime: ModelTestStreamRuntime,
    context: RequestContext,
) -> str:
    try:
        cancellation_id_value = context.cancellation_id
    except AttributeError:
        cancellation_id_value = None
    cancellation_id = normalize_cancellation_id(cancellation_id_value)
    if cancellation_id:
        return cancellation_id
    generated_cancellation_id = create_system_id(
        subsystem="ws_model_test",
        owner=runtime.run_id,
        include_random_suffix=True,
    )
    context.cancellation_id = generated_cancellation_id
    return generated_cancellation_id


async def run_ws_model_test_stream(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    runtime: ModelTestStreamRuntime,
    request_json: JSONDict,
) -> None:
    logger = get_logger(LOGGER_NAME)
    event_bus = api_context.dependencies.event_bus
    accepted_task_id: str | None = None
    base_context = request.state.context
    context = clone_request_context(base_context, task_id=None)
    base_cancellation_id = _resolve_model_test_cancellation_id(
        runtime=runtime,
        context=context,
    )
    model_id = resolve_optional_model_name(request_json)
    stream_transcript = OpenAIStreamTranscript(model_hint=model_id)
    detached = False

    try:
        task_metadata: JSONDict = {"run_id": runtime.run_id, "model_test": True}
        if model_id is not None:
            task_metadata["model"] = model_id
        bundle = await create_streaming_inference_task(
            api_context.dependencies,
            context=context,
            request_json=request_json,
            task_type=TASK_TYPE_CHAT_COMPLETION,
            user_id=runtime.user_id,
            owner_type="system",
            owner_id=runtime.run_id,
            cancellation_id=extend_soai_id(
                base_cancellation_id,
                ("model_test", runtime.run_id),
            ),
            metadata=task_metadata,
            request_source=REQUEST_SOURCE_MODEL_TEST,
        )
        task = bundle.task
        runtime.active_task_id = task.task_id
        accepted_task_id = task.task_id
        reply_queue = bundle.reply_queue
        context.task_id = task.task_id
        if openai_ws_detach_event_is_set(runtime.detach_event):
            detached = True
            schedule_ws_model_test_stream_cancel(
                api_context=api_context,
                request=request,
                runtime=runtime,
                reason="Model test stream cancelled before startup completed.",
            )
            return
        stream_gen = create_stream_generator(
            reply_queue,
            stream_dependencies,
            api_context.dependencies,
            context,
            stream_transcript=stream_transcript,
            model=model_id,
            include_usage=True,
            emit_done_marker=True,
            max_completion_tokens=resolve_request_max_completion_tokens(request_json),
        )
        async for chunk in stream_gen:
            if openai_ws_detach_event_is_set(runtime.detach_event):
                detached = True
                schedule_ws_model_test_stream_cancel(
                    api_context=api_context,
                    request=request,
                    runtime=runtime,
                    reason="Model test stream cancelled during streaming.",
                )
                break
            if not isinstance(chunk, bytes | bytearray | memoryview):
                continue
            parsed_error = parse_openai_sse_error_frame(bytes(chunk))
            if parsed_error is not None:
                raise_openai_streaming_error(parsed_error, operation=OPERATION)
            decoded = decode_sse_chunk_bytes(chunk)
            if decoded is None:
                continue
            if process_openai_stream_frame(decoded).done_marker_observed:
                break
            visible_deltas = stream_transcript.drain_visible_text_deltas()
            if not visible_deltas:
                continue
            delta_text = "".join(visible_deltas)
            if not delta_text:
                continue
            await publish_model_test_stream_event(
                event_bus,
                runtime,
                event_type="assistant_text_delta",
                payload={"delta": delta_text},
            )
        if detached or openai_ws_detach_event_is_set(runtime.detach_event):
            return
        if accepted_task_id is not None:
            await raise_terminal_model_test_task_error(
                api_context=api_context,
                task_id=accepted_task_id,
                operation=OPERATION,
            )
        if openai_ws_detach_event_is_set(runtime.detach_event):
            return
        await publish_model_test_stream_completion(
            event_bus=event_bus,
            runtime=runtime,
            stream_transcript=stream_transcript,
        )
    except SoAIError as exception:
        if accepted_task_id is not None:
            schedule_ws_model_test_stream_cancel(
                api_context=api_context,
                request=request,
                runtime=runtime,
                reason="Model test stream failed after task admission.",
            )
        if int(exception.http_status) >= 500:
            log_exception(
                logger,
                exception,
                message="Model test stream failed.",
                trace_id=context.trace_id,
                operation=OPERATION,
                level="warning",
                details={"run_id": runtime.run_id},
            )
        else:
            log_handled_exception(
                logger,
                exception,
                message="Model test stream rejected a client request.",
                trace_id=context.trace_id,
                operation=OPERATION,
                level="debug",
                details={"run_id": runtime.run_id},
            )
        await publish_model_test_stream_error(
            event_bus=event_bus,
            runtime=runtime,
            exception=exception,
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exception:
        if accepted_task_id is not None:
            schedule_ws_model_test_stream_cancel(
                api_context=api_context,
                request=request,
                runtime=runtime,
                reason="Model test stream failed after task admission.",
            )
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Model test stream failed.",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="error",
            details={"run_id": runtime.run_id},
        )
        await publish_model_test_stream_error(
            event_bus=event_bus,
            runtime=runtime,
            exception=coerced,
        )


def schedule_ws_model_test_stream_cancel(
    *,
    api_context: ApiContext,
    request: RequestProtocol,
    runtime: ModelTestStreamRuntime,
    reason: str,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    active_task_id = runtime.active_task_id
    if not active_task_id:
        return False
    normalized_reason = (
        reason.strip() if reason.strip() else "Model test stream cancellation requested."
    )
    context = request.state.context
    return schedule_streaming_task_cancel(
        registry=api_context.dependencies.task_registry,
        task_id=active_task_id,
        reason=normalized_reason,
        context=context,
        logger=logger,
        operation="model_test_stream.cancel",
        track_background_task=api_context.dependencies.application_control.track_background_task,
    )
