"""SoAI - MCP runtime pruning and output methods [backend/mcp/tools/runtime_session_pruning_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections import deque

from mcp.tools.internal_protocols import MCPToolRuntimeSessionShellStoreProtocol
from mcp.tools.runtime_session_shell_methods import (
    queue_session_for_terminal_close,
    touch_shell_session,
)
from mcp.tools.runtime_types import ShellSession

__all__ = (
    "drain_shell_output",
    "pop_shell_sessions_pending_terminal_close",
    "prune_shell_sessions",
    "snapshot_shell_output",
)


def _chunk_text_length(chunk: bytes) -> int:
    try:
        return len(chunk.decode("utf-8", errors="replace"))
    except UnicodeError:
        return len(chunk)


def _is_long_lived_shell_session(session: ShellSession) -> bool:
    return session.run_in_background or session.background_watch_started


def _collect_output_text(
    chunks: deque[bytes],
    *,
    start_offset: int,
    max_chars: int,
) -> tuple[str, int]:
    collected: list[bytes] = []
    collected_chars = 0
    consumed_count = 0
    for chunk_offset, chunk in enumerate(chunks):
        if chunk_offset < start_offset:
            continue
        if collected_chars >= max_chars:
            break
        consumed_count += 1
        if not chunk:
            continue
        collected.append(chunk)
        collected_chars += _chunk_text_length(chunk)
    return b"".join(collected).decode("utf-8", errors="replace"), consumed_count


def prune_shell_sessions(self: MCPToolRuntimeSessionShellStoreProtocol) -> None:
    now = time.monotonic()
    expired_closed_session_ids: list[int] = []
    expired_active_session_ids: list[int] = []
    for session_id, session in self.shell_sessions.items():
        if session.exit_code is None:
            if _is_long_lived_shell_session(session):
                continue
            if (now - session.last_touched_monotonic) >= self.SHELL_SESSION_ACTIVE_IDLE_TTL_SEC:
                expired_active_session_ids.append(session_id)
            continue
        if (now - session.last_touched_monotonic) >= self.SHELL_SESSION_EXIT_TTL_SEC:
            expired_closed_session_ids.append(session_id)
    for session_id in expired_closed_session_ids:
        removed = self.shell_sessions.pop(session_id, None)
        if removed is not None:
            self.remove_shell_transcript(removed.session_id)
            queue_session_for_terminal_close(self, removed)
    for session_id in expired_active_session_ids:
        removed = self.shell_sessions.pop(session_id, None)
        if removed is not None:
            self.remove_shell_transcript(removed.session_id)
            queue_session_for_terminal_close(self, removed)
    sessions_by_owner: dict[str, list[ShellSession]] = {}
    for session in self.shell_sessions.values():
        owner_sessions = sessions_by_owner.get(session.owner_key)
        if owner_sessions is None:
            owner_sessions = []
            sessions_by_owner[session.owner_key] = owner_sessions
        owner_sessions.append(session)
    for owner_sessions in sessions_by_owner.values():
        owner_count = len(owner_sessions)
        if owner_count <= self.SHELL_SESSION_MAX_PER_OWNER:
            continue
        closed_sessions = sorted(
            [session for session in owner_sessions if session.exit_code is not None],
            key=lambda session: session.last_touched_monotonic,
        )
        active_sessions = sorted(
            [
                session
                for session in owner_sessions
                if session.exit_code is None and not _is_long_lived_shell_session(session)
            ],
            key=lambda session: session.last_touched_monotonic,
        )
        for session in [*closed_sessions, *active_sessions]:
            if owner_count <= self.SHELL_SESSION_MAX_PER_OWNER:
                break
            removed = self.shell_sessions.pop(session.session_id, None)
            if removed is not None:
                self.remove_shell_transcript(removed.session_id)
                queue_session_for_terminal_close(self, removed)
            owner_count -= 1


def drain_shell_output(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    max_chars: int,
) -> str:
    session = self.shell_sessions.get(session_id)
    if session is None:
        return ""
    touch_shell_session(session)
    max_chars = max(0, int(max_chars))
    if max_chars == 0 or not session.output:
        return ""
    start_offset = max(0, session.output_drain_sequence - session.output_start_sequence)
    output, consumed_count = _collect_output_text(
        session.output,
        start_offset=start_offset,
        max_chars=max_chars,
    )
    session.output_drain_sequence += consumed_count
    return output


def snapshot_shell_output(
    self: MCPToolRuntimeSessionShellStoreProtocol,
    session_id: int,
    max_chars: int,
) -> str:
    session = self.shell_sessions.get(session_id)
    if session is None:
        return ""
    touch_shell_session(session)
    max_chars = max(0, int(max_chars))
    if max_chars == 0 or not session.output:
        return ""
    return _collect_output_text(
        session.output,
        start_offset=0,
        max_chars=max_chars,
    )[0]


def pop_shell_sessions_pending_terminal_close(
    self: MCPToolRuntimeSessionShellStoreProtocol,
) -> list[ShellSession]:
    self.prune_shell_sessions()
    pending = list(self.pending_terminal_close_sessions.values())
    self.pending_terminal_close_sessions = {}
    return pending
