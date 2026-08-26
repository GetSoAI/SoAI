"""SoAI - Strict OpenAI Responses non-streaming result handling [backend/features/api/routes/openai/responses/passthrough_non_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_tasks import TaskCompleteEvent
from core.logging.trace import get_logger
from core.openai.response_terminal_policy import (
    is_terminal_response_payload,
    response_status_from_event,
)
from core.openai.responses_events import build_response_event_from_json
from core.openai.responses_provider_events import ResponsesProviderStreamError
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.types.json_value import coerce_json_dict
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.routes.openai.chat.chat_ops import (
    get_effective_routing_config,
    resolve_non_streaming_timeout,
)
from features.api.routes.openai.non_streaming_event_loop import (
    run_non_streaming_event_loop,
)
from features.api.routes.openai.responses.effective_input_state import (
    require_effective_input_items,
)
from features.api.routes.openai.responses.passthrough_response_setup import (
    prepare_responses_passthrough_response_setup,
)
from features.api.routes.openai.responses.passthrough_task_setup import (
    ResponsesTaskSetupResult,
)
from features.api.routes.openai.responses.provider_chunk_validation import (
    validate_responses_provider_chunk,
)
from features.api.routes.openai.responses.provider_error_details import (
    ResponsesProviderErrorDetails,
    extract_provider_error_details,
)
from features.api.routes.openai.responses.response_event_storage import (
    ResponseStorageTarget,
    normalize_stored_response_event,
    persist_normalized_response_event,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.response_body import create_json_body_response
from features.api.runtime.responses import (
    apply_operation_id_header,
    apply_task_id_header,
)
from features.api.streaming.stream_dependencies import build_stream_dependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("wait_for_non_streaming_responses_result",)

OPERATION = "api_openai.responses.passthrough_non_streaming.wait_for_non_streaming_responses_result"


LOGGER_NAME = "SoAI.features.api.passthrough_non_streaming"


def _require_terminal_response(event_payload: JSONDict) -> JSONDict:
    response_value = event_payload.get("response")
    response = coerce_json_dict(response_value)
    if response is None:
        raise StateError("Provider returned a malformed terminal Responses event.")
    return response


async def wait_for_non_streaming_responses_result(
    *,
    request: Request,
    api_context: ApiContext,
    task_setup: ResponsesTaskSetupResult,
    request_json: JSONDict,
) -> JSONResponse:
    logger = get_logger(LOGGER_NAME)
    context = request.state.context
    stream_dependencies = build_stream_dependencies(api_context.dependencies)
    reply_queue = task_setup.reply_channel
    task = task_setup.task
    timeout = resolve_non_streaming_timeout(get_effective_routing_config(api_context), None)

    accumulator = OpenAISSEFrameAccumulator()
    buffered_response_event: JSONDict | None = None
    buffered_failed_error: ResponsesProviderErrorDetails | None = None
    response_setup = prepare_responses_passthrough_response_setup(
        request=request,
        task_id=task.task_id,
        request_json=request_json,
    )
    provider_state = response_setup.provider_state

    async def on_inference_result(result_event: InferenceResultEvent) -> JSONDict:
        accumulator.finalize()
        payload_value = result_event.payload
        payload = coerce_json_dict(payload_value)
        if payload is None:
            raise StateError("Provider returned a non-object Responses result payload.")
        return payload

    async def on_stream_chunk(result_event: StreamChunkEvent) -> None:
        nonlocal buffered_response_event
        nonlocal buffered_failed_error
        validated_chunk = validate_responses_provider_chunk(
            accumulator,
            result_event.chunk,
            terminal_observed=buffered_response_event is not None,
        )
        for event_payload in validated_chunk.payloads:
            provider_state.observe(event_payload)
            error_value = event_payload.get("error")
            error_dict = coerce_json_dict(error_value)
            if error_dict is not None:
                buffered_failed_error = extract_provider_error_details(error_dict)
            if is_terminal_response_payload(event_payload):
                buffered_response_event = event_payload
                response = _require_terminal_response(event_payload)
                if (
                    response_status_from_event(event_payload, default_status="completed")
                    == "failed"
                ):
                    error_value = response.get("error")
                    error_dict = coerce_json_dict(error_value)
                    if error_dict is not None:
                        buffered_failed_error = extract_provider_error_details(error_dict)

    async def on_stream_end(_event: StreamEndEvent) -> JSONDict:
        accumulator.finalize()
        if buffered_response_event is not None:
            return _require_terminal_response(buffered_response_event)
        if buffered_failed_error is not None:
            return {}
        synthesized_response = provider_state.build_response_json(status="completed")
        return synthesized_response or {}

    async def on_task_complete(task_complete_event: TaskCompleteEvent) -> JSONDict:
        if task_complete_event.success:
            accumulator.finalize()
        if buffered_response_event is not None:
            return _require_terminal_response(buffered_response_event)
        if buffered_failed_error is not None:
            return {}
        if not task_complete_event.success:
            raise StateError(task_complete_event.message or "Task failed.")
        synthesized_response = provider_state.build_response_json(status="completed")
        return synthesized_response or {}

    async def on_unknown_event(_event: Event) -> None:
        return None

    try:
        payload = await run_non_streaming_event_loop(
            request=request,
            stream_dependencies=stream_dependencies,
            reply_queue=reply_queue,
            task_id=task.task_id,
            timeout=timeout,
            on_inference_result=on_inference_result,
            on_stream_chunk=on_stream_chunk,
            on_stream_end=on_stream_end,
            on_task_complete=on_task_complete,
            on_unknown_event=on_unknown_event,
        )
    except ResponsesProviderStreamError as exception:
        return build_openai_error_json_response(
            status_code=502,
            message=str(exception),
            canonical_error_type="server_error",
            param=None,
            code=None,
            trace_id=context.trace_id,
            headers=None,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION,
            trace_id=context.trace_id,
        )
        log_exception(
            logger,
            coerced,
            message="Responses non-streaming request failed.",
            trace_id=context.trace_id,
            operation=OPERATION,
            details={"task_id": task.task_id},
            level="warning",
        )
        try:
            status_raw = coerced.http_status
        except AttributeError:
            status_raw = 500
        status_code = int(status_raw or 500)
        message = "Internal server error." if status_code >= 500 else str(coerced)
        return build_openai_error_json_response(
            status_code=status_code,
            message=message,
            canonical_error_type="server_error",
            param=None,
            code=None,
            trace_id=context.trace_id,
            headers=None,
        )

    if payload:
        payload_response_event = build_response_event_from_json(response_json=payload)
        storage_target = ResponseStorageTarget(
            response_id=provider_state.response_id,
            task_id=task.task_id,
            user_id=response_setup.user_id,
            api_key_id=response_setup.api_key_id,
            model=provider_state.model,
            created_at=response_setup.created_at,
            is_background=False,
            stream_enabled=False,
        )
        stored_event = normalize_stored_response_event(
            target=storage_target,
            payload=payload_response_event,
            sequence_number=0,
            default_status="completed",
        )
        if response_setup.store:
            input_items_to_store = require_effective_input_items(request)
            await persist_normalized_response_event(
                api_context=api_context,
                target=storage_target,
                stored_event=stored_event,
                sequence_number=0,
                input_items=input_items_to_store,
                reset_events=True,
            )
        response_json = stored_event.response_json
        response = create_json_body_response(content=response_json)
        apply_task_id_header(response, task.task_id)
        apply_operation_id_header(response, context.trace_id)
        return response
    if buffered_failed_error is not None:
        return build_openai_error_json_response(
            status_code=502,
            message=buffered_failed_error.message,
            canonical_error_type="server_error",
            param=None,
            code=buffered_failed_error.code,
            trace_id=context.trace_id,
            headers=None,
        )
    return build_openai_error_json_response(
        status_code=502,
        message="Provider did not return a Responses result payload.",
        canonical_error_type="server_error",
        param=None,
        code=None,
        trace_id=context.trace_id,
        headers=None,
    )
