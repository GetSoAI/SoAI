"""SoAI - MCP server session manager [backend/mcp/server/handlers/session_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cleanup_guards import cleanup_no_raise
from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.mcp.protocol_versions import validate_protocol_version
from mcp.protocol.types import MCPClientSession, MCPJSONRPCError
from mcp.server.handlers.session_activity import touch_session_last_activity

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.server.state import MCPServerState

__all__ = (
    "MCPSessionManager",
    "MCPSessionManagerDependencies",
)

LOGGER_NAME = "SoAI.mcp.server.session_manager"


@dataclass(frozen=True, slots=True)
class MCPSessionManagerDependencies:
    state: MCPServerState
    session_ttl_sec: int
    cleanup_pruned_shell_sessions: Callable[[], Awaitable[int]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPSessionManagerDependencies",
            cleanup_pruned_shell_sessions=self.cleanup_pruned_shell_sessions,
            session_ttl_sec=self.session_ttl_sec,
            state=self.state,
        )


class MCPSessionManager:
    def __init__(self, deps: MCPSessionManagerDependencies) -> None:
        self._state = deps.state
        self._session_ttl_sec = deps.session_ttl_sec
        self._cleanup_pruned_shell_sessions = deps.cleanup_pruned_shell_sessions

    def generate_session_id(self) -> str:
        return f"soai_{uuid.uuid4().hex}"

    async def ensure_client_session(
        self,
        session_id: str,
        protocol_version: str | None = None,
        user_id: int = 0,
        create_if_missing: bool = True,
    ) -> str:
        version_valid, negotiated = validate_protocol_version(protocol_version)
        if not version_valid:
            raise MCPJSONRPCError(-32602, f"Unsupported protocol version: {protocol_version}")
        session_state = self._state.session
        async with session_state.client_sessions_lock:
            if session_id not in session_state.client_sessions:
                if not create_if_missing:
                    raise MCPJSONRPCError(-32602, "MCP session not found")
                session_state.client_sessions[session_id] = MCPClientSession(
                    client_id=session_id,
                    session_id=session_id,
                    user_id=user_id,
                    protocol_version=negotiated,
                )
            else:
                session = session_state.client_sessions[session_id]
                session.protocol_version = negotiated
                if user_id != 0 and session.user_id == 0:
                    session.user_id = user_id
        await touch_session_last_activity(session_state, session_id)
        return negotiated

    async def has_client_session(self, session_id: str) -> bool:
        async with self._state.session.client_sessions_lock:
            return session_id in self._state.session.client_sessions

    async def close_client_session(self, session_id: str) -> None:
        session_state = self._state.session
        streaming_state = self._state.streaming
        registration_state = self._state.registration
        async with session_state.client_sessions_lock:
            session = session_state.client_sessions.get(session_id)
            if session and session.client_id != session_id:
                session_state.client_to_session.pop(session.client_id, None)
            queue = streaming_state.notification_queues.pop(session_id, None)
            session_state.client_sessions.pop(session_id, None)
            streaming_state.stream_consumer_counts.pop(session_id, None)
            streaming_state.sse_event_counters.pop(session_id, None)
            streaming_state.sse_replay_buffers.pop(session_id, None)
        if queue:
            self._close_notification_queue(queue, session_id)
        async with registration_state.resource_subscriptions_lock:
            registration_state.resource_subscriptions.pop(session_id, None)

    async def close_all_client_sessions(self) -> None:
        async with self._state.session.client_sessions_lock:
            session_ids = list(self._state.session.client_sessions.keys())
        for session_id in session_ids:
            await self.close_client_session(session_id)

    def _close_notification_queue(
        self,
        queue: asyncio.Queue[JSONDict | None],
        session_id: str,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        attempts = max(1, int(queue.maxsize)) if queue.maxsize > 0 else 1
        overwrite_result = put_nowait_with_overwrite(queue, None, overwrite_attempts=attempts)
        if not overwrite_result.delivered:
            logger.warning("Notification queue full for session %s; forcing close", session_id)

    def get_session_user_id(self, session_id: str) -> int:
        session = self.get_session(session_id)
        return session.user_id if session else 0

    def resolve_session_id(self, client_id: str) -> str:
        if not client_id:
            return client_id
        return self._state.session.client_to_session.get(client_id, client_id)

    def get_session(self, session_id: str | None) -> MCPClientSession | None:
        if not session_id:
            return None
        return self._state.session.client_sessions.get(session_id)

    async def update_session_activity(self, session_id: str) -> None:
        await touch_session_last_activity(self._state.session, session_id)

    async def _close_session_if_stale(self, session_id: str, cutoff: float) -> bool:
        session_state = self._state.session
        streaming_state = self._state.streaming
        registration_state = self._state.registration
        async with session_state.client_sessions_lock:
            session = session_state.client_sessions.get(session_id)
            if not session or session.last_activity >= cutoff:
                return False
            if session.client_id != session_id:
                session_state.client_to_session.pop(session.client_id, None)
            queue = streaming_state.notification_queues.pop(session_id, None)
            session_state.client_sessions.pop(session_id, None)
            streaming_state.stream_consumer_counts.pop(session_id, None)
            streaming_state.sse_event_counters.pop(session_id, None)
            streaming_state.sse_replay_buffers.pop(session_id, None)
        if queue:
            self._close_notification_queue(queue, session_id)
        async with registration_state.resource_subscriptions_lock:
            registration_state.resource_subscriptions.pop(session_id, None)
        return True

    async def close_inactive_sessions(self) -> None:
        logger = get_logger(LOGGER_NAME)
        cutoff = time.monotonic() - self._session_ttl_sec
        stale_sessions: list[str] = []
        async with self._state.session.client_sessions_lock:
            for session_id, session in self._state.session.client_sessions.items():
                if session.last_activity < cutoff:
                    stale_sessions.append(session_id)
        closed_count = 0
        for session_id in stale_sessions:
            if await self._close_session_if_stale(session_id, cutoff):
                closed_count += 1
        if closed_count > 0:
            logger.debug("Closed %d inactive MCP sessions", closed_count)

    async def session_cleanup_loop(self, sweep_interval_sec: int) -> None:
        logger = get_logger(LOGGER_NAME)
        while not self._state.shutdown_event.is_set():
            await self.close_inactive_sessions()
            closed_shell_sessions = await cleanup_no_raise(
                self._cleanup_pruned_shell_sessions(),
                logger=logger,
                message="Failed to cleanup pruned MCP shell sessions (non-critical).",
                operation="mcp.server.session_manager.session_cleanup_loop.cleanup_pruned_shell_sessions",
                level="warning",
            )
            if isinstance(closed_shell_sessions, int) and closed_shell_sessions > 0:
                logger.debug("Closed %d pruned MCP shell sessions", closed_shell_sessions)
            try:
                await asyncio.wait_for(
                    self._state.shutdown_event.wait(),
                    timeout=float(sweep_interval_sec),
                )
            except TimeoutError:
                continue
