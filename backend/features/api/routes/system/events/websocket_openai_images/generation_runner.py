"""SoAI - WebSocket OpenAI images generation runner [backend/features/api/routes/system/events/websocket_openai_images/generation_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.routes.system.events.websocket_openai_images.payloads import (
    build_openai_images_generation_completed,
    build_openai_images_generation_error,
    build_openai_images_generation_stream_chunk,
)
from features.api.routes.system.events.websocket_openai_images.result_collection import (
    collect_openai_image_generation_result,
)
from features.api.routes.system.events.websocket_openai_runner_failure_handling import (
    openai_ws_detach_event_is_set,
)
from features.api.runtime.event_enqueue import enqueue_correlated_media_event
from features.api.streaming.openai_stream_generator.generator import (
    create_stream_generator,
)
from features.api.streaming.stream_cancel import schedule_streaming_task_cancel

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.runtime.request_context import RequestContext
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection
    from features.api.streaming.websocket_openai_runtime import (
        OpenAiImageGenerationRuntime,
    )

__all__ = ("run_openai_images_generation",)

LOGGER_NAME = "SoAI.features.api.generation_runner"
OPERATION_IMAGES_GENERATION_CANCEL = "api_system.websocket.openai_images.generation.cancel"
OPERATION_IMAGES_GENERATION_RUN = "api_system.websocket.openai_images.generation.run"


async def run_openai_images_generation(
    *,
    run_id: str,
    runtime: OpenAiImageGenerationRuntime,
    runtimes: dict[str, OpenAiImageGenerationRuntime],
    connection: WebsocketConnection,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    request_context: RequestContext,
    reply_queue: asyncio.Queue[Event],
    task_id: str,
    model_id: str | None,
    stream_enabled: bool,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    shutdown_event: asyncio.Event,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        if stream_enabled:
            generator = create_stream_generator(
                reply_queue,
                stream_dependencies,
                api_context.dependencies,
                request_context,
                task_id=task_id,
                model=model_id,
                include_usage=False,
                emit_done_marker=True,
                allow_image_events=True,
            )
            sequence = 0
            async for chunk in generator:
                if openai_ws_detach_event_is_set(runtime.detach_event):
                    schedule_streaming_task_cancel(
                        registry=api_context.dependencies.task_registry,
                        task_id=task_id,
                        reason="WebSocket images generation cancelled.",
                        context=request_context,
                        logger=logger,
                        operation=OPERATION_IMAGES_GENERATION_CANCEL,
                        track_background_task=(
                            api_context.dependencies.application_control.track_background_task
                        ),
                    )
                    return
                if not isinstance(chunk, bytes | bytearray | memoryview):
                    continue
                text = bytes(chunk).decode("utf-8", errors="replace")
                if not text:
                    continue
                delivered = await enqueue_correlated_media_event(
                    enqueue_warning_tracker,
                    connection.queue,
                    build_openai_images_generation_stream_chunk(
                        run_id=run_id,
                        sequence=sequence,
                        chunk=text,
                    ),
                    shutdown_event,
                    "OpenAI images generation chunk",
                )
                if not delivered:
                    return
                sequence += 1
            await enqueue_correlated_media_event(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_images_generation_completed(
                    run_id=run_id,
                    task_id=task_id,
                    chunk_count=sequence,
                ),
                shutdown_event,
                "OpenAI images generation completed",
            )
            return
        result = await collect_openai_image_generation_result(
            reply_queue=reply_queue,
            timeout_seconds=120.0,
        )
        await enqueue_correlated_media_event(
            enqueue_warning_tracker,
            connection.queue,
            build_openai_images_generation_completed(
                run_id=run_id,
                task_id=task_id,
                chunk_count=0,
                result=result,
            ),
            shutdown_event,
            "OpenAI images generation completed",
        )
    except asyncio.CancelledError:
        if not openai_ws_detach_event_is_set(runtime.detach_event):
            raise
        return
    except RECOVERABLE_EXCEPTIONS as exception:
        if openai_ws_detach_event_is_set(runtime.detach_event):
            return
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_IMAGES_GENERATION_RUN,
        )
        log_exception(
            logger,
            exception,
            message="OpenAI images generation failed.",
            operation=OPERATION_IMAGES_GENERATION_RUN,
            trace_id=trace_id,
            level="error",
        )
        await enqueue_correlated_media_event(
            enqueue_warning_tracker=enqueue_warning_tracker,
            queue=connection.queue,
            event=build_openai_images_generation_error(
                run_id=run_id,
                message=str(coerced),
                code=str(coerced.code),
                task_id=task_id,
            ),
            shutdown_event=shutdown_event,
            context_label="OpenAI images generation error",
        )
    finally:
        if runtimes.get(run_id) is runtime:
            runtimes.pop(run_id, None)
