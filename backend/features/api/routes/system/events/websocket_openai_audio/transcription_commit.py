"""SoAI - WebSocket OpenAI transcription commit handler [backend/features/api/routes/system/events/websocket_openai_audio/transcription_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.upload_staging import cleanup_temp_file
from core.runtime.protocols import RequestProtocol
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_transcription_error,
)
from features.api.routes.system.events.websocket_openai_audio.runtime import (
    guard_openai_audio_transcription_run_start,
    with_locked_active_transcription_runtime,
)
from features.api.routes.system.events.websocket_openai_audio.transcription_runner import (
    run_openai_audio_transcription,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_openai_audio.runtime import (
        OpenAiAudioTranscriptionRuntime,
    )
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import (
        WebsocketConnection,
        WebSocketRequestAdapter,
    )

__all__ = ("handle_openai_audio_transcription_commit",)


async def _discard_unscheduled_transcription(
    *,
    run_id: str,
    runtime: OpenAiAudioTranscriptionRuntime,
    transcriptions: dict[str, OpenAiAudioTranscriptionRuntime],
) -> None:
    runtime.state = "failed"
    await cleanup_temp_file(runtime.temp_path)
    if transcriptions.get(run_id) is runtime:
        transcriptions.pop(run_id, None)


async def handle_openai_audio_transcription_commit(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    del request_adapter
    transcription_run_id = await guard_openai_audio_transcription_run_start(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
    )
    if transcription_run_id is None:
        return
    run_id = transcription_run_id

    async def _handle_locked_transcription(
        transcriptions: dict[str, OpenAiAudioTranscriptionRuntime],
        runtime: OpenAiAudioTranscriptionRuntime,
    ) -> None:
        if runtime.state != "uploading" or (
            runtime.runner_task is not None and not runtime.runner_task.done()
        ):
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message="Transcription already running.",
                    code="conflict_error",
                ),
                "OpenAI audio transcription error",
            )
            return
        runtime.state = "committed"
        runtime.sealed_bytes = runtime.received_bytes
        try:
            runner_task = api_context.dependencies.application_control.schedule_background_task(
                run_openai_audio_transcription(
                    run_id=run_id,
                    runtime=runtime,
                    transcriptions=transcriptions,
                    connection=connection,
                    request_context=request.state.context,
                    api_context=api_context,
                    enqueue_warning_tracker=enqueue_warning_tracker,
                    trace_id=trace_id,
                ),
                name=f"ws_openai_audio_transcription:{run_id}",
            )
        except RECOVERABLE_EXCEPTIONS:
            await _discard_unscheduled_transcription(
                run_id=run_id,
                runtime=runtime,
                transcriptions=transcriptions,
            )
            raise
        if runner_task is None:
            await _discard_unscheduled_transcription(
                run_id=run_id,
                runtime=runtime,
                transcriptions=transcriptions,
            )
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                build_openai_audio_transcription_error(
                    run_id=run_id,
                    message="Transcription runner could not be scheduled.",
                    code="server_error",
                ),
                "OpenAI audio transcription error",
            )
            return
        runtime.runner_task = runner_task

    await with_locked_active_transcription_runtime(
        run_id=run_id,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        handler=_handle_locked_transcription,
    )
