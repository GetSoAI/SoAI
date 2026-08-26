"""SoAI - MCP runtime shell session methods [backend/mcp/tools/runtime_session_shell_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from core.errors.exceptions import ValidationError
from mcp.tools.internal_protocols import MCPToolRuntimeSessionShellStoreProtocol
from mcp.tools.runtime_types import ShellSession

__all__ = (
    "append_shell_output",
    "close_shell_session",
    "close_shell_session_and_queue_terminal_close",
    "create_shell_session",
    "get_shell_session",
    "list_shell_sessions_for_owner",
    "list_shell_sessions_for_user",
    "mark_shell_exit",
    "peek_shell_session_exit",
    "queue_session_for_terminal_close",
    "requeue_shell_session_for_terminal_close",
    "touch_shell_session",
)


def touch_shell_session(session: ShellSession) -> None:
    session.last_touched_monotonic = time.monotonic()


def queue_session_for_terminal_close(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session: ShellSession,
) -> None:
    if session.terminal_session_finalized:
        return
    self.pending_terminal_close_sessions[session.terminal_session_id] = session


def create_shell_session(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    terminal_session_id: str,
    owner_key: str | None = None,
) -> ShellSession:
    normalized_terminal_id = (
        terminal_session_id.strip() if isinstance(terminal_session_id, str) else ""
    )
    if not normalized_terminal_id:
        raise ValidationError("terminal_session_id must be a non-empty string.")
    resolved_owner = (
        owner_key.strip()
        if isinstance(owner_key, str) and owner_key.strip()
        else self.current_owner_key()
    )
    self.prune_shell_sessions()
    session_id = self.next_session_id
    self.next_session_id += 1
    session = ShellSession(
        session_id=session_id,
        terminal_session_id=normalized_terminal_id,
        owner_key=resolved_owner,
        user_id=self.current_user_id(),
    )
    self.shell_sessions[session_id] = session
    self.prune_shell_sessions()
    return session


def get_shell_session(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
) -> ShellSession | None:
    self.prune_shell_sessions()
    session = self.shell_sessions.get(session_id)
    if session is None:
        return None
    touch_shell_session(session)
    return session


def close_shell_session(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
) -> ShellSession | None:
    session = self.shell_sessions.pop(session_id, None)
    if session is None:
        return None
    self.remove_shell_transcript(session.session_id)
    if session.terminal_session_finalized:
        self.pending_terminal_close_sessions.pop(session.terminal_session_id, None)
    else:
        queue_session_for_terminal_close(self, session)
    return session


def close_shell_session_and_queue_terminal_close(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
) -> ShellSession | None:
    session = self.shell_sessions.pop(session_id, None)
    if session is None:
        return None
    self.remove_shell_transcript(session.session_id)
    queue_session_for_terminal_close(self, session)
    return session


def requeue_shell_session_for_terminal_close(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session: ShellSession,
) -> None:
    queue_session_for_terminal_close(self, session)


def list_shell_sessions_for_owner(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    owner_key: str | None = None,
) -> list[ShellSession]:
    resolved_owner = (
        owner_key.strip()
        if isinstance(owner_key, str) and owner_key.strip()
        else self.current_owner_key()
    )
    self.prune_shell_sessions()
    return [
        session for session in self.shell_sessions.values() if session.owner_key == resolved_owner
    ]


def list_shell_sessions_for_user(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    user_id: int,
) -> list[ShellSession]:
    self.prune_shell_sessions()
    return [session for session in self.shell_sessions.values() if session.user_id == user_id]


def append_shell_output(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    data: bytes,
) -> None:
    session = self.shell_sessions.get(session_id)
    if session is None or not data:
        return
    touch_shell_session(session)
    self.append_shell_transcript_output(session_id, data)
    session.output.append(data)
    session.output_bytes += len(data)
    session.output_next_sequence += 1
    while session.output and session.output_bytes > self.SHELL_SESSION_MAX_OUTPUT_BYTES:
        removed = session.output.popleft()
        session.output_bytes = max(0, session.output_bytes - len(removed))
        session.output_start_sequence += 1
    session.output_drain_sequence = max(
        session.output_drain_sequence,
        session.output_start_sequence,
    )
    session.output_drain_sequence = min(
        session.output_drain_sequence,
        session.output_next_sequence,
    )


def mark_shell_exit(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    exit_code: int,
) -> None:
    session = self.shell_sessions.get(session_id)
    if session is None:
        return
    touch_shell_session(session)
    session.exit_code = int(exit_code)


def peek_shell_session_exit(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
) -> tuple[bool, int | None]:
    self.prune_shell_sessions()
    session = self.shell_sessions.get(session_id)
    if session is None:
        return (False, None)
    return (True, session.exit_code)
