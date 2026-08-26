"""SoAI - WebSocket connection lifecycle for the realtime events API [backend/features/api/streaming/websocket.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from fastapi import WebSocket
from starlette.datastructures import Headers, State

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.runtime.protocols import RequestProtocol
from core.runtime.proxy_headers import resolve_client_ip_from_chain
from core.state.access import AccessAction
from features.api.middleware.security.networks import is_ip_network_tuple
from features.api.runtime.app_state_access import require_app_state
from features.api.runtime.context import ApiContext

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_model_test_stream.state import (
        ModelTestStreamRuntime,
    )
    from features.api.streaming.websocket_openai_runtime import (
        OpenAiAudioSpeechRuntime,
        OpenAiAudioSpeechSessionRuntime,
        OpenAiAudioTranscriptionRuntime,
        OpenAiImageGenerationRuntime,
    )
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "WebSocketRequestAdapter",
    "WebsocketConnection",
    "resolve_websocket_client_host",
    "resolve_websocket_close_code",
)


def resolve_websocket_close_code(status_code: int) -> int:
    match status_code:
        case 401:
            return 4001
        case 403:
            return 4003
        case 429:
            return 4029
        case _:
            return 4001


def resolve_websocket_client_host(websocket: WebSocket) -> str:
    try:
        headers = websocket.headers
    except AttributeError:
        headers = Headers({})
    if not headers:
        headers = Headers({})
    try:
        client = websocket.client
    except AttributeError:
        client = None
    if client is None:
        host = None
    else:
        try:
            host = client.host
        except AttributeError:
            host = None
    if not host:
        return "unknown"
    app_state = require_app_state(websocket)
    try:
        proxy_enabled = bool(app_state.proxy_headers_enabled)
    except AttributeError as exception:
        raise StateError("Proxy header runtime state is not configured.") from exception
    try:
        trusted_networks = app_state.trusted_proxy_networks
    except AttributeError as exception:
        raise StateError("Trusted proxy networks are not configured.") from exception
    if not is_ip_network_tuple(trusted_networks):
        raise StateError("Trusted proxy networks are not configured.")
    resolved = resolve_client_ip_from_chain(host, headers, trusted_networks, proxy_enabled)
    return resolved or host


class WebSocketRequestAdapter:

    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket
        self.url = websocket.url
        self.scope = websocket.scope
        self.method = "GET"
        self.headers = websocket.headers
        self.cookies = websocket.cookies
        self.client = websocket.client
        self.app = websocket.app
        try:
            state_obj = websocket.state
        except AttributeError:
            state_obj = None
        if state_obj is None:
            state_obj = State()
            if "state" not in websocket.scope:
                websocket.scope["state"] = state_obj
        self.state = state_obj


class WebsocketConnection:

    def __init__(
        self,
        websocket: WebSocket,
        request: RequestProtocol,
        api_context: ApiContext,
        user: JSONDict,
        granted_actions: frozenset[AccessAction],
        event_permissions: Mapping[type[Event], AccessAction],
        logger: LoggerProtocol,
        jti: str,
        trace_id: str | None = None,
    ) -> None:
        self.websocket = websocket
        self.request = request
        self.api_context = api_context
        self.user = user
        self.granted_actions = granted_actions
        self._event_permissions = event_permissions
        self._logger = logger
        self.trace_id = trace_id
        self.jti = jti
        self.close_code = 1000
        self.close_reason = ""
        self.session_revalidation_deadline = time.monotonic() + 300.0
        self.chat_streams: dict[str, AssistantTimelineRuntime] = {}
        self.model_test_streams: dict[str, ModelTestStreamRuntime] = {}
        self.openai_audio_transcriptions: dict[str, OpenAiAudioTranscriptionRuntime] = {}
        self.openai_audio_speech_streams: dict[str, OpenAiAudioSpeechRuntime] = {}
        self.openai_audio_speech_sessions: dict[str, OpenAiAudioSpeechSessionRuntime] = {}
        self.openai_image_generations: dict[str, OpenAiImageGenerationRuntime] = {}
        self.queue: asyncio.Queue[JSONDict] = asyncio.Queue(maxsize=5000)
        self.subscribed_types: set[type[Event]] = set()
        self.resource_interests: set[str] = set()
        self.resource_interest_event_types: set[type[Event]] = set()
        self.resource_interest_generation = 0
        self.chat_presentation_conversation_id: str | None = None
        self.event_handler: Callable[[Event], Awaitable[None]] | None = None
        self.snapshot_tasks: dict[str, asyncio.Task[None]] = {}
        self.log_streams: dict[str, asyncio.Task[None] | None] = {}
        self.log_stream_replacements: set[str] = set()
        self.pty_session_id: str | None = None
        self.conversation_presence_device_id: str | None = None
        self.conversation_presence_tab_id: str | None = None

    def can_receive_event(self, event_type: type[Event]) -> bool:
        if event_type not in self._event_permissions:
            self._logger.warning(
                "Websocket event type %s not in websocket event permission map. This is a programming error - all event types must be explicitly mapped.",
                event_type.__name__,
            )
            return False
        required_action = self._event_permissions[event_type]
        return required_action in self.granted_actions
