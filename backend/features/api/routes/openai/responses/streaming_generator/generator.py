"""SoAI - OpenAI Responses streaming handlers [backend/features/api/routes/openai/responses/streaming_generator/generator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from fastapi import Request

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_models_streaming import StreamChunkEvent, StreamEndEvent
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.logging.trace import get_logger
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_frames import sse_done_chunk, sse_keepalive_chunk
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from features.api.routes.openai.responses.effective_input_state import (
    require_effective_input_items,
)
from features.api.routes.openai.responses.passthrough_response_setup import (
    prepare_responses_passthrough_response_setup,
)
from features.api.routes.openai.responses.passthrough_task_setup import (
    ResponsesTaskSetupResult,
)
from features.api.routes.openai.responses.streaming_generator.exit_persistence import (
    flush_response_stream_on_exit,
    persist_cancellation_on_stream_exit,
    persist_failure_after_stream_error,
)
from features.api.routes.openai.responses.streaming_generator.passthrough_persistence import (
    ResponsesPassthroughPersistence,
)
from features.api.routes.openai.responses.streaming_generator.provider_chunk_processing import (
    collect_provider_chunk_response_events,
    finalize_provider_sse_stream,
)
from features.api.routes.openai.responses.streaming_generator.terminal_events import (
    emit_failure_done,
    emit_synthesized_completion_or_failure,
)
from features.api.routes.openai.responses.streaming_generator.timed_stream_iteration import (
    iter_openai_classified_items_with_flush_timer,
)
from features.api.runtime.context import ApiContext
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.api.streaming.stream_iteration import (
    StreamTermination,
    iter_openai_sse_classified_stream_events_with_keepalive_chunks,
)

__all__ = ()

LOGGER_NAME = "SoAI.features.api.streaming_generator_generator"
OPERATION_OPENAI_RESPONSES_STREAM_GENERATOR_PERSISTENCE = "openai.responses.streaming.persistence"


async def responses_passthrough_stream_generator(
    *,
    task_setup: ResponsesTaskSetupResult,
    api_context: ApiContext,
    request: Request,
    request_json: JSONDict,
) -> AsyncGenerator[bytes]:
    logger = get_logger(LOGGER_NAME)
    done_chunk = sse_done_chunk()
    context = request.state.context
    stream_dependencies = build_stream_dependencies(api_context.dependencies)
    reply_queue = task_setup.reply_channel
    task = task_setup.task
    try:
        user_id_value = context.user_id
    except AttributeError:
        user_id_value = 0
    user_id = int(user_id_value) if is_strict_int(user_id_value) else 0
    stream_dependencies.task_registry.bind_reply_queue_identity(
        reply_queue,
        task_id=task.task_id,
        user_id=user_id,
    )
    stream_completed = False
    validated_provider_output = False
    input_items = require_effective_input_items(request)
    accumulator = OpenAISSEFrameAccumulator()
    response_setup = prepare_responses_passthrough_response_setup(
        request=request,
        task_id=task.task_id,
        request_json=request_json,
    )
    persistence = ResponsesPassthroughPersistence(
        api_context=api_context,
        task_id=task.task_id,
        api_key_id=response_setup.api_key_id,
        store=response_setup.store,
        input_items=input_items,
        response_event_sequence=0,
        recorded_response_id=response_setup.response_id,
        storage_target=response_setup.storage_target(
            task_id=task.task_id,
            stream_enabled=True,
        ),
    )
    provider_state = response_setup.provider_state

    stream_iter = iter_openai_sse_classified_stream_events_with_keepalive_chunks(
        reply_queue,
        stream_dependencies,
        context,
        keepalive_chunk=sse_keepalive_chunk(),
    )

    try:
        async for item in iter_openai_classified_items_with_flush_timer(
            stream_iter,
            should_flush=lambda: bool(persistence.store and persistence.has_pending_events),
            flush_interval_ms=int(persistence.flush_interval_ms),
            flush=lambda: persistence.flush_if_needed(force=False),
        ):
            if isinstance(item, StreamTermination):
                classified = item
                if stream_completed:
                    break
                message = classified.message or "Stream terminated."
                code = classified.error_code or "server_error"
                async for chunk in emit_failure_done(
                    persistence=persistence,
                    done_chunk=done_chunk,
                    code=code,
                    message=message,
                ):
                    yield chunk
                stream_completed = True
                break
            if isinstance(item, bytes):
                await persistence.flush_if_needed(force=False)
                yield item
                continue
            stream_event = item
            event = stream_event.event
            if isinstance(event, StreamChunkEvent):
                if event.chunk:
                    chunk_result = await collect_provider_chunk_response_events(
                        chunk=event.chunk,
                        accumulator=accumulator,
                        provider_state=provider_state,
                        persistence=persistence,
                        done_chunk=done_chunk,
                    )
                    if chunk_result.observed_provider_payload:
                        validated_provider_output = True
                    for chunk in chunk_result.emitted_chunks:
                        yield chunk
                    if chunk_result.terminal:
                        stream_completed = True
                        return
                continue
            if isinstance(event, StreamEndEvent):
                if not stream_completed:
                    framing_failure_chunks = await finalize_provider_sse_stream(
                        accumulator=accumulator,
                        persistence=persistence,
                        done_chunk=done_chunk,
                    )
                    if framing_failure_chunks:
                        for chunk in framing_failure_chunks:
                            yield chunk
                        stream_completed = True
                        break
                    if validated_provider_output:
                        async for chunk in emit_synthesized_completion_or_failure(
                            provider_state=provider_state,
                            persistence=persistence,
                            done_chunk=done_chunk,
                            message=(
                                "Provider ended the Responses stream without a terminal "
                                "response event."
                            ),
                        ):
                            yield chunk
                    else:
                        async for chunk in emit_failure_done(
                            persistence=persistence,
                            done_chunk=done_chunk,
                            code="server_error",
                            message="Provider did not return a Responses stream.",
                        ):
                            yield chunk
                    stream_completed = True
                break
            if isinstance(event, TaskCompleteEvent):
                if not event.success and not stream_completed:
                    message = event.message or "Streaming request failed."
                    async for chunk in emit_failure_done(
                        persistence=persistence,
                        done_chunk=done_chunk,
                        code="server_error",
                        message=message,
                    ):
                        yield chunk
                    stream_completed = True
                if not stream_completed:
                    framing_failure_chunks = await finalize_provider_sse_stream(
                        accumulator=accumulator,
                        persistence=persistence,
                        done_chunk=done_chunk,
                    )
                    if framing_failure_chunks:
                        for chunk in framing_failure_chunks:
                            yield chunk
                        stream_completed = True
                        break
                    async for chunk in emit_synthesized_completion_or_failure(
                        provider_state=provider_state,
                        persistence=persistence,
                        done_chunk=done_chunk,
                        message="Task completed without a terminal Responses event.",
                    ):
                        yield chunk
                    stream_completed = True
                break
            if isinstance(event, ErrorEvent):
                if not stream_completed:
                    message = event.message or "Streaming request failed."
                    try:
                        code = event.error_type.value
                    except AttributeError:
                        code = "server_error"
                    async for chunk in emit_failure_done(
                        persistence=persistence,
                        done_chunk=done_chunk,
                        code=str(code),
                        message=str(message),
                    ):
                        yield chunk
                    stream_completed = True
                break
            if isinstance(event, TaskProgressEvent):
                continue
            logger.debug(
                "[%s] Responses passthrough stream ignoring event type: %s",
                context.trace_id,
                type(event).__name__,
            )
    except asyncio.CancelledError:
        if persistence.store and not stream_completed:
            await persist_cancellation_on_stream_exit(
                persistence=persistence,
                logger=logger,
                context=context,
                task_id=task.task_id,
            )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_OPENAI_RESPONSES_STREAM_GENERATOR_PERSISTENCE,
            trace_id=context.trace_id,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to persist response events.",
            operation=OPERATION_OPENAI_RESPONSES_STREAM_GENERATOR_PERSISTENCE,
            trace_id=context.trace_id,
            details={
                "task_id": str(task.task_id),
                "response_id": persistence.recorded_response_id,
            },
        )
        failed_chunk, terminal_chunk = await persist_failure_after_stream_error(
            persistence=persistence,
            logger=logger,
            context=context,
            task_id=task.task_id,
            done_chunk=done_chunk,
        )
        yield failed_chunk
        yield terminal_chunk
        return
    finally:
        if persistence.store and not stream_completed:
            await flush_response_stream_on_exit(
                persistence=persistence,
                logger=logger,
                context=context,
                task_id=task.task_id,
            )
