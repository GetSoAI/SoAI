"""SoAI - Internal WebSocket protocol constants for system events [backend/features/api/routes/system/events/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import (
        WebsocketConnection,
        WebSocketRequestAdapter,
    )

__all__ = (
    "WEBSOCKET_LOG_STREAM_EVENT_TYPES",
    "WEBSOCKET_MCP_REALTIME_EVENT_TYPES",
    "WEBSOCKET_PROTOCOL_VERSION",
    "WEBSOCKET_PTY_EVENT_TYPES",
    "OpenAiWsErrorPayloadBuilder",
    "WebSocketEventTypes",
    "WebSocketMessageTypes",
    "WebsocketEventHandlerWithRequestAdapter",
)

WEBSOCKET_PROTOCOL_VERSION: Final[int] = 1


class WebSocketMessageTypes:
    PONG: Final[str] = "pong"
    LATENCY_PROBE: Final[str] = "latency_probe"
    REQUEST_SNAPSHOT: Final[str] = "request_snapshot"
    SET_RESOURCE_INTERESTS: Final[str] = "set_resource_interests"
    SUBSCRIBE_LOG_STREAM: Final[str] = "subscribe_log_stream"
    UNSUBSCRIBE_LOG_STREAM: Final[str] = "unsubscribe_log_stream"
    CHAT_STREAM_START: Final[str] = "chat_stream_start"
    CHAT_STREAM_CANCEL: Final[str] = "chat_stream_cancel"
    CHAT_TOKEN_COUNT: Final[str] = "chat_token_count"
    CONVERSATION_PRESENCE_UPDATE: Final[str] = "conversation_presence_update"
    CONVERSATION_ATTENTION_MARK_SEEN: Final[str] = "conversation_attention_mark_seen"
    MODEL_TEST_STREAM_START: Final[str] = "model_test_stream_start"
    MODEL_TEST_STREAM_CANCEL: Final[str] = "model_test_stream_cancel"
    PTY_CONNECT: Final[str] = "pty_connect"
    PTY_INPUT: Final[str] = "pty_input"
    PTY_RESIZE: Final[str] = "pty_resize"
    PTY_DISCONNECT: Final[str] = "pty_disconnect"
    UPDATE_OPENAI_API_KEY_QUOTA: Final[str] = "update_openai_api_key_quota"
    UPDATE_USER_WORKSPACE_PATH: Final[str] = "update_user_workspace_path"
    OPENAI_AUDIO_TRANSCRIPTION_START: Final[str] = "openai_audio_transcription_start"
    OPENAI_AUDIO_TRANSCRIPTION_CHUNK: Final[str] = "openai_audio_transcription_chunk"
    OPENAI_AUDIO_TRANSCRIPTION_COMMIT: Final[str] = "openai_audio_transcription_commit"
    OPENAI_AUDIO_TRANSCRIPTION_CANCEL: Final[str] = "openai_audio_transcription_cancel"
    OPENAI_AUDIO_SPEECH_START: Final[str] = "openai_audio_speech_start"
    OPENAI_AUDIO_SPEECH_CANCEL: Final[str] = "openai_audio_speech_cancel"
    OPENAI_AUDIO_SPEECH_SESSION_START: Final[str] = "openai_audio_speech_session_start"
    OPENAI_AUDIO_SPEECH_SESSION_SEGMENT: Final[str] = "openai_audio_speech_session_segment"
    OPENAI_AUDIO_SPEECH_SESSION_FINISH: Final[str] = "openai_audio_speech_session_finish"
    OPENAI_AUDIO_SPEECH_SESSION_CANCEL: Final[str] = "openai_audio_speech_session_cancel"
    OPENAI_IMAGES_GENERATION_START: Final[str] = "openai_images_generation_start"
    OPENAI_IMAGES_GENERATION_CANCEL: Final[str] = "openai_images_generation_cancel"
    PLUGIN_BACKEND_INSTALL: Final[str] = "plugin_backend_install"
    PLUGIN_BACKEND_REMOVE: Final[str] = "plugin_backend_remove"
    PLUGIN_BACKEND_UPDATE: Final[str] = "plugin_backend_update"
    MODEL_DOWNLOAD: Final[str] = "model_download"


class WebSocketEventTypes:
    CHAT_STREAM_COMMAND_ERROR: Final[str] = "chat_stream_command_error"
    CHAT_TOKEN_COUNT_RESULT: Final[str] = "chat_token_count_result"
    CHAT_TOKEN_COUNT_ERROR: Final[str] = "chat_token_count_error"
    COMMAND_ACCEPTED: Final[str] = "command_accepted"
    INVALID_REQUEST: Final[str] = "invalid_request"
    FORBIDDEN: Final[str] = "forbidden"
    NOT_FOUND: Final[str] = "not_found"
    CONFLICT: Final[str] = "conflict"
    SERVER_ERROR: Final[str] = "server_error"
    INVALID_RESOURCE_INTEREST: Final[str] = "invalid_resource_interest"
    RESOURCE_INTERESTS_APPLIED: Final[str] = "resource_interests_applied"
    UNKNOWN_MESSAGE: Final[str] = "unknown_message"
    OPENAI_API_KEY_QUOTA_UPDATED: Final[str] = "openai_api_key_quota_updated"
    MCP_NOTIFICATION: Final[str] = "MCPNotificationEvent"
    MCP_TOOLS_LIST_CHANGED: Final[str] = "MCPToolsListChangedEvent"
    MCP_RESOURCES_LIST_CHANGED: Final[str] = "MCPResourcesListChangedEvent"
    MCP_PROMPTS_LIST_CHANGED: Final[str] = "MCPPromptsListChangedEvent"
    MCP_SERVER_STARTED: Final[str] = "MCPServerStartedEvent"
    MCP_SERVER_ADDED: Final[str] = "MCPServerAddedEvent"
    MCP_SERVER_REMOVED: Final[str] = "MCPServerRemovedEvent"
    MCP_SERVER_CONNECTED: Final[str] = "MCPServerConnectedEvent"
    MCP_SERVER_DISCONNECTED: Final[str] = "MCPServerDisconnectedEvent"
    MCP_TOOL_INVOKED: Final[str] = "MCPToolInvokedEvent"
    PTY_CONNECTED: Final[str] = "pty_connected"
    PTY_OUTPUT: Final[str] = "pty_output"
    PTY_EXITED: Final[str] = "pty_exited"
    PTY_DISCONNECTED: Final[str] = "pty_disconnected"
    PTY_ERROR: Final[str] = "pty_error"
    PTY_BUSY: Final[str] = "pty_busy"
    LOG_BATCH: Final[str] = "log_batch"
    LOG_STREAM_SUBSCRIBED: Final[str] = "log_stream_subscribed"
    LOG_STREAM_UNSUBSCRIBED: Final[str] = "log_stream_unsubscribed"
    LOG_STREAM_RECONFIGURED: Final[str] = "log_stream_reconfigured"
    LOG_STREAM_CLOSED: Final[str] = "log_stream_closed"
    LOG_STREAM_ERROR: Final[str] = "log_stream_error"
    SNAPSHOT_RESPONSE: Final[str] = "snapshot_response"
    SNAPSHOT_ERROR: Final[str] = "snapshot_error"
    PING: Final[str] = "ping"
    LATENCY_PROBE_RESULT: Final[str] = "latency_probe_result"
    OPENAI_AUDIO_TRANSCRIPTION_STARTED: Final[str] = "openai_audio_transcription_started"
    OPENAI_AUDIO_TRANSCRIPTION_COMPLETED: Final[str] = "openai_audio_transcription_completed"
    OPENAI_AUDIO_TRANSCRIPTION_CANCELLED: Final[str] = "openai_audio_transcription_cancelled"
    OPENAI_AUDIO_TRANSCRIPTION_ERROR: Final[str] = "openai_audio_transcription_error"
    OPENAI_AUDIO_SPEECH_STARTED: Final[str] = "openai_audio_speech_started"
    OPENAI_AUDIO_SPEECH_CHUNK: Final[str] = "openai_audio_speech_chunk"
    OPENAI_AUDIO_SPEECH_COMPLETED: Final[str] = "openai_audio_speech_completed"
    OPENAI_AUDIO_SPEECH_CANCELLED: Final[str] = "openai_audio_speech_cancelled"
    OPENAI_AUDIO_SPEECH_ERROR: Final[str] = "openai_audio_speech_error"
    OPENAI_AUDIO_SPEECH_SESSION_STARTED: Final[str] = "openai_audio_speech_session_started"
    OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_STARTED: Final[str] = (
        "openai_audio_speech_session_segment_started"
    )
    OPENAI_AUDIO_SPEECH_SESSION_CHUNK: Final[str] = "openai_audio_speech_session_chunk"
    OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_COMPLETED: Final[str] = (
        "openai_audio_speech_session_segment_completed"
    )
    OPENAI_AUDIO_SPEECH_SESSION_COMPLETED: Final[str] = "openai_audio_speech_session_completed"
    OPENAI_AUDIO_SPEECH_SESSION_CANCELLED: Final[str] = "openai_audio_speech_session_cancelled"
    OPENAI_AUDIO_SPEECH_SESSION_ERROR: Final[str] = "openai_audio_speech_session_error"
    OPENAI_IMAGES_GENERATION_STARTED: Final[str] = "openai_images_generation_started"
    OPENAI_IMAGES_GENERATION_STREAM_CHUNK: Final[str] = "openai_images_generation_stream_chunk"
    OPENAI_IMAGES_GENERATION_COMPLETED: Final[str] = "openai_images_generation_completed"
    OPENAI_IMAGES_GENERATION_CANCELLED: Final[str] = "openai_images_generation_cancelled"
    OPENAI_IMAGES_GENERATION_ERROR: Final[str] = "openai_images_generation_error"


class WebsocketEventHandlerWithRequestAdapter(Protocol):
    def __call__(
        self,
        data: JSONDict,
        *,
        connection: WebsocketConnection,
        request: RequestProtocol,
        request_adapter: WebSocketRequestAdapter,
        api_context: ApiContext,
        enqueue_warning_tracker: EnqueueWarningTracker,
        trace_id: str | None,
    ) -> Awaitable[None]: ...


class OpenAiWsErrorPayloadBuilder(Protocol):
    def __call__(
        self,
        *,
        run_id: str,
        message: str,
        code: str,
        task_id: str | None = None,
    ) -> JSONDict: ...


WEBSOCKET_MCP_REALTIME_EVENT_TYPES: Final[tuple[str, ...]] = (
    WebSocketEventTypes.MCP_NOTIFICATION,
    WebSocketEventTypes.MCP_TOOLS_LIST_CHANGED,
    WebSocketEventTypes.MCP_RESOURCES_LIST_CHANGED,
    WebSocketEventTypes.MCP_PROMPTS_LIST_CHANGED,
    WebSocketEventTypes.MCP_SERVER_STARTED,
    WebSocketEventTypes.MCP_SERVER_ADDED,
    WebSocketEventTypes.MCP_SERVER_REMOVED,
    WebSocketEventTypes.MCP_SERVER_CONNECTED,
    WebSocketEventTypes.MCP_SERVER_DISCONNECTED,
    WebSocketEventTypes.MCP_TOOL_INVOKED,
)


WEBSOCKET_PTY_EVENT_TYPES: Final[tuple[str, ...]] = (
    WebSocketEventTypes.PTY_CONNECTED,
    WebSocketEventTypes.PTY_OUTPUT,
    WebSocketEventTypes.PTY_EXITED,
    WebSocketEventTypes.PTY_DISCONNECTED,
    WebSocketEventTypes.PTY_ERROR,
    WebSocketEventTypes.PTY_BUSY,
)


WEBSOCKET_LOG_STREAM_EVENT_TYPES: Final[tuple[str, ...]] = (
    WebSocketEventTypes.LOG_BATCH,
    WebSocketEventTypes.LOG_STREAM_SUBSCRIBED,
    WebSocketEventTypes.LOG_STREAM_CLOSED,
    WebSocketEventTypes.LOG_STREAM_UNSUBSCRIBED,
    WebSocketEventTypes.LOG_STREAM_RECONFIGURED,
    WebSocketEventTypes.LOG_STREAM_ERROR,
)
