"""SoAI - WebSocket system events runtime context [backend/features/api/routes/system/events/websocket_event_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from features.api.routes.system.events.internal_protocols import (
    WebsocketEventHandlerWithRequestAdapter,
)

if TYPE_CHECKING:
    from fastapi import WebSocket

    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import (
        WebsocketConnection,
        WebSocketRequestAdapter,
    )

__all__ = ("WebsocketEventRuntimeContext",)


@dataclass(frozen=True, slots=True)
class WebsocketEventRuntimeContext:
    websocket: WebSocket
    request: RequestProtocol
    request_adapter: WebSocketRequestAdapter
    api_context: ApiContext
    connection: WebsocketConnection
    stream_dependencies: StreamDependencies
    shutdown_event: asyncio.Event
    enqueue_warning_tracker: EnqueueWarningTracker
    trace_id: str | None

    async def invoke_with_request_adapter(
        self,
        handler: WebsocketEventHandlerWithRequestAdapter,
        data: JSONDict,
    ) -> None:
        await handler(
            data,
            connection=self.connection,
            request=self.request,
            request_adapter=self.request_adapter,
            api_context=self.api_context,
            enqueue_warning_tracker=self.enqueue_warning_tracker,
            trace_id=self.trace_id,
        )

    def with_shutdown_event(self, shutdown_event: asyncio.Event) -> WebsocketEventRuntimeContext:
        return WebsocketEventRuntimeContext(
            websocket=self.websocket,
            request=self.request,
            request_adapter=self.request_adapter,
            api_context=self.api_context,
            connection=self.connection,
            stream_dependencies=self.stream_dependencies,
            shutdown_event=shutdown_event,
            enqueue_warning_tracker=self.enqueue_warning_tracker,
            trace_id=self.trace_id,
        )
