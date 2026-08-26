"""SoAI - MCP server streaming and SSE replay manager [backend/mcp/server/handlers/streaming_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.locks import bounded_lock_for_cleanup
from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
)
from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.di.validation import require_dependencies
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_NOTIFICATIONS_DROPPED,
)
from core.types.json import JSONDict
from mcp.protocol.types import MCPJSONRPCError
from mcp.server.handlers.session_activity import touch_session_last_activity

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol
    from mcp.server.state import MCPServerState

__all__ = (
    "MCPStreamingService",
    "MCPStreamingServiceDependencies",
)

LOGGER_NAME = "SoAI.mcp.server.streaming_service"


@dataclass(frozen=True, slots=True)
class MCPStreamingServiceDependencies:
    state: MCPServerState
    notification_queue_size: int
    sse_replay_buffer_size: int
    metrics_manager: MetricsManagerProtocol
    close_client_session: Callable[[str], Awaitable[None]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPStreamingServiceDependencies",
            close_client_session=self.close_client_session,
            metrics_manager=self.metrics_manager,
            notification_queue_size=self.notification_queue_size,
            sse_replay_buffer_size=self.sse_replay_buffer_size,
            state=self.state,
        )


_MCP_NOTIFICATION_BACKPRESSURE_TIMEOUT_SECONDS: float = 0.0
_MCP_NOTIFICATION_DROP_WARNING_INTERVAL_SECONDS: float = 30.0


class MCPStreamingService:
    def __init__(self, deps: MCPStreamingServiceDependencies) -> None:
        self._state = deps.state
        self._notification_queue_size = deps.notification_queue_size
        self._sse_replay_buffer_size = deps.sse_replay_buffer_size
        self._metrics_manager = deps.metrics_manager
        self._close_client_session = deps.close_client_session
        self._notification_drop_tracker = QueueDropTracker(
            _MCP_NOTIFICATION_DROP_WARNING_INTERVAL_SECONDS,
        )

    def _log_notification_drop(
        self,
        logger: StandardLogger,
        session_id: str,
        queue: asyncio.Queue[JSONDict | None],
        dropped_count: int,
    ) -> None:
        normalized_dropped_count = max(1, int(dropped_count))
        queue_cap = queue.maxsize if queue.maxsize > 0 else "unbounded"
        log_queue_drop_with_tracker(
            logger,
            self._notification_drop_tracker,
            normalized_dropped_count,
            f"Notification queue full for session {session_id} (size={queue.qsize()}/{queue_cap})",
        )
        self._metrics_manager.increment_counter(
            *MCP_SERVER_COUNTER_NOTIFICATIONS_DROPPED,
            value=normalized_dropped_count,
        )

    async def has_active_client_stream(self, session_id: str) -> bool:
        async with self._state.session.client_sessions_lock:
            return self._state.streaming.stream_consumer_counts.get(session_id, 0) > 0

    def _parse_sse_event_counter(self, session_id: str, event_id: str | None) -> int | None:
        if not event_id or not isinstance(event_id, str):
            return None
        prefix = f"{session_id}:"
        counter_text = event_id[len(prefix) :] if event_id.startswith(prefix) else ""
        return int(counter_text) if counter_text.isdigit() else None

    async def sync_sse_event_counter_from_last_event_id(
        self,
        session_id: str,
        last_event_id: str | None,
    ) -> None:
        counter = self._parse_sse_event_counter(session_id, last_event_id)
        async with self._state.session.client_sessions_lock:
            streaming = self._state.streaming
            if counter is not None and counter > streaming.sse_event_counters.get(session_id, 0):
                streaming.sse_event_counters[session_id] = counter

    async def _increment_sse_counter(self, session_id: str, payload: JSONDict | None = None) -> str:
        async with self._state.session.client_sessions_lock:
            streaming = self._state.streaming
            streaming.sse_event_counters[session_id] = (
                streaming.sse_event_counters.get(session_id, 0) + 1
            )
            counter = streaming.sse_event_counters[session_id]
            event_id = f"{session_id}:{counter}"
            if payload is not None:
                buffer = streaming.sse_replay_buffers.get(session_id)
                if buffer is None:
                    buffer = deque[tuple[int, JSONDict]](maxlen=int(self._sse_replay_buffer_size))
                    streaming.sse_replay_buffers[session_id] = buffer
                buffer.append((counter, payload))
            return event_id

    async def allocate_sse_event_id(self, session_id: str, payload: JSONDict) -> str:
        if not session_id:
            raise MCPJSONRPCError(-32602, "session_id is required")
        if not isinstance(payload, dict):
            raise MCPJSONRPCError(-32602, "payload must be an object")
        return await self._increment_sse_counter(session_id, payload=payload)

    async def get_sse_replay_events(
        self,
        session_id: str,
        last_event_id: str | None,
    ) -> list[tuple[str, JSONDict]]:
        last_counter = self._parse_sse_event_counter(session_id, last_event_id)
        async with self._state.session.client_sessions_lock:
            buffer = self._state.streaming.sse_replay_buffers.get(session_id)
            if last_counter is None or not buffer:
                return []
            return [
                (f"{session_id}:{counter}", payload)
                for counter, payload in buffer
                if counter > last_counter
            ]

    async def _get_notification_queue(self, session_id: str) -> asyncio.Queue[JSONDict | None]:
        async with self._state.session.client_sessions_lock:
            if session_id not in self._state.session.client_sessions:
                raise MCPJSONRPCError(-32603, f"Session not found: {session_id}")
            streaming = self._state.streaming
            if session_id not in streaming.notification_queues:
                streaming.notification_queues[session_id] = asyncio.Queue(
                    maxsize=self._notification_queue_size,
                )
            return streaming.notification_queues[session_id]

    async def emit_client_stream_message(self, session_id: str, message: JSONDict) -> None:
        logger = get_logger(LOGGER_NAME)
        queue = await self._get_notification_queue(session_id)
        delivery = await put_with_backpressure(
            queue,
            message,
            self._state.shutdown_event,
            backpressure_timeout=_MCP_NOTIFICATION_BACKPRESSURE_TIMEOUT_SECONDS,
        )
        if delivery.status in (
            BackpressureDeliveryStatus.DELIVERED,
            BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
        ):
            return
        self._log_notification_drop(logger, session_id, queue, delivery.dropped_count)
        logger.warning(
            "Client notification queue full for session %s, closing session",
            session_id,
        )
        await self._close_client_session(session_id)
        raise MCPJSONRPCError(
            -32000,
            f"Client backpressure: notification queue full for session {session_id}",
        )

    async def try_emit_client_stream_message(self, session_id: str, message: JSONDict) -> bool:
        logger = get_logger(LOGGER_NAME)
        queue: asyncio.Queue[JSONDict | None] | None = None
        async with self._state.session.client_sessions_lock:
            session_state = self._state.session
            streaming = self._state.streaming
            if session_id not in session_state.client_sessions:
                return False
            consumer_count = streaming.stream_consumer_counts.get(session_id, 0)
            if consumer_count <= 0:
                return False
            queue = streaming.notification_queues.get(session_id)
            if queue is None:
                return False
        if queue is None:
            return False
        delivery = await put_with_backpressure(
            queue,
            message,
            self._state.shutdown_event,
            backpressure_timeout=_MCP_NOTIFICATION_BACKPRESSURE_TIMEOUT_SECONDS,
        )
        if delivery.status in (
            BackpressureDeliveryStatus.DELIVERED,
            BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
        ):
            return True
        self._log_notification_drop(logger, session_id, queue, delivery.dropped_count)
        logger.warning("Client notification queue full for session %s, closing session", session_id)
        await self._close_client_session(session_id)
        return False

    async def get_client_notification_stream(
        self,
        session_id: str,
        shutdown_events: tuple[asyncio.Event, ...] = (),
    ) -> AsyncGenerator[JSONDict | None]:
        logger = get_logger(LOGGER_NAME)
        queue = await self._get_notification_queue(session_id)
        active_shutdown_events = tuple(
            shutdown_event
            for shutdown_event in shutdown_events
            if isinstance(shutdown_event, asyncio.Event)
        )
        async with self._state.session.client_sessions_lock:
            streaming = self._state.streaming
            streaming.stream_consumer_counts[session_id] = (
                streaming.stream_consumer_counts.get(session_id, 0) + 1
            )
        try:
            while (not self._state.shutdown_event.is_set()) and all(
                not shutdown_event.is_set() for shutdown_event in active_shutdown_events
            ):
                async with self._state.session.client_sessions_lock:
                    session_exists = session_id in self._state.session.client_sessions
                if not session_exists:
                    logger.debug(
                        "Session %s closed, terminating notification stream",
                        session_id,
                    )
                    break
                race_result = await race_queue_operation_against_signals(
                    queue.get(),
                    (self._state.shutdown_event, *active_shutdown_events),
                    timeout_seconds=30.0,
                )
                if race_result.outcome is QueueRaceOutcome.OPERATION_COMPLETED:
                    await touch_session_last_activity(self._state.session, session_id)
                    yield race_result.value
                    continue
                if race_result.outcome is QueueRaceOutcome.SIGNAL_FIRED:
                    break
                if race_result.outcome is QueueRaceOutcome.TIMEOUT:
                    async with self._state.session.client_sessions_lock:
                        session_exists = session_id in self._state.session.client_sessions
                    if session_exists:
                        await touch_session_last_activity(self._state.session, session_id)
                        yield None
                    else:
                        break
        finally:
            async with bounded_lock_for_cleanup(
                self._state.session.client_sessions_lock,
            ) as lock_result:
                if lock_result.acquired:
                    streaming = self._state.streaming
                    count = streaming.stream_consumer_counts.get(session_id, 0)
                    if count > 0:
                        streaming.stream_consumer_counts[session_id] = count - 1
                    if streaming.stream_consumer_counts.get(session_id, 0) == 0:
                        streaming.stream_consumer_counts.pop(session_id, None)
