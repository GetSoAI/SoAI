"""SoAI - WebSocket dispatching for OpenAI audio messages [backend/features/api/routes/system/events/websocket_message_dispatch_openai_audio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.websocket_openai_audio.speech_handlers import (
    handle_openai_audio_speech_cancel,
    handle_openai_audio_speech_start,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_commands import (
    handle_openai_audio_speech_session_cancel,
    handle_openai_audio_speech_session_finish,
    handle_openai_audio_speech_session_segment,
)
from features.api.routes.system.events.websocket_openai_audio.speech_session_start import (
    handle_openai_audio_speech_session_start,
)
from features.api.routes.system.events.websocket_openai_audio.transcription_commit import (
    handle_openai_audio_transcription_commit,
)
from features.api.routes.system.events.websocket_openai_audio.transcription_upload_chunks import (
    handle_openai_audio_transcription_cancel,
    handle_openai_audio_transcription_chunk,
)
from features.api.routes.system.events.websocket_openai_audio.transcription_upload_start import (
    handle_openai_audio_transcription_start,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("try_handle_openai_audio_message",)


async def try_handle_openai_audio_message(
    message_type: str,
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    match message_type:
        case WebSocketMessageTypes.OPENAI_AUDIO_TRANSCRIPTION_START:
            await handle_openai_audio_transcription_start(
                data,
                connection=runtime_context.connection,
                request=runtime_context.request,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_TRANSCRIPTION_CHUNK:
            await handle_openai_audio_transcription_chunk(
                data,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_TRANSCRIPTION_COMMIT:
            await runtime_context.invoke_with_request_adapter(
                handle_openai_audio_transcription_commit,
                data,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_TRANSCRIPTION_CANCEL:
            await handle_openai_audio_transcription_cancel(
                data,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_SPEECH_START:
            await handle_openai_audio_speech_start(
                data,
                connection=runtime_context.connection,
                request=runtime_context.request,
                api_context=runtime_context.api_context,
                stream_dependencies=runtime_context.stream_dependencies,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
                shutdown_event=runtime_context.shutdown_event,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_SPEECH_CANCEL:
            await handle_openai_audio_speech_cancel(
                data,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_SPEECH_SESSION_START:
            await handle_openai_audio_speech_session_start(
                data,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                stream_dependencies=runtime_context.stream_dependencies,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
                trace_id=runtime_context.trace_id,
                shutdown_event=runtime_context.shutdown_event,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT:
            await handle_openai_audio_speech_session_segment(
                data,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_SPEECH_SESSION_FINISH:
            await handle_openai_audio_speech_session_finish(
                data,
                connection=runtime_context.connection,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
            )
            return True
        case WebSocketMessageTypes.OPENAI_AUDIO_SPEECH_SESSION_CANCEL:
            await handle_openai_audio_speech_session_cancel(
                data,
                connection=runtime_context.connection,
                api_context=runtime_context.api_context,
                enqueue_warning_tracker=runtime_context.enqueue_warning_tracker,
            )
            return True
        case _:
            return False
