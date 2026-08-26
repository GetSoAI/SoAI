"""SoAI - MCP utility tool runtime session state [backend/mcp/tools/runtime_sessions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from mcp.tools.runtime_session_pruning_methods import (
    drain_shell_output,
    pop_shell_sessions_pending_terminal_close,
    prune_shell_sessions,
    snapshot_shell_output,
)
from mcp.tools.runtime_session_shell_methods import (
    append_shell_output,
    close_shell_session,
    close_shell_session_and_queue_terminal_close,
    create_shell_session,
    get_shell_session,
    list_shell_sessions_for_owner,
    list_shell_sessions_for_user,
    mark_shell_exit,
    peek_shell_session_exit,
    requeue_shell_session_for_terminal_close,
)
from mcp.tools.runtime_session_transcript_methods import (
    append_shell_transcript_output,
    create_shell_transcript,
    read_shell_transcript_incremental,
    read_shell_transcript_lines,
    remove_shell_transcript,
    search_shell_transcript,
    snapshot_shell_transcript_page,
)
from mcp.tools.runtime_session_workspace_methods import (
    get_or_create_workspace_state,
    prune_workspace_states,
    set_workspace_path,
)
from mcp.tools.runtime_types import ShellSession, ToolWorkspaceState

if TYPE_CHECKING:
    from core.mcp.protocols_main import ShellTranscriptProtocol

__all__ = (
    "ShellSession",
    "MCPToolRuntimeSessionStore",
    "ToolWorkspaceState",
)


class MCPToolRuntimeSessionStore:
    SHELL_SESSION_EXIT_TTL_SEC: float = 300.0
    SHELL_SESSION_ACTIVE_IDLE_TTL_SEC: float = 3600.0
    SHELL_SESSION_MAX_PER_OWNER: int = 128
    SHELL_SESSION_MAX_OUTPUT_BYTES: int = 2 * MIB_BYTES
    WORKSPACE_IDLE_TTL_SEC: float = 3600.0
    WORKSPACE_MAX_PER_PROCESS: int = 4096

    def __init__(
        self,
        *,
        config: ConfigProtocol,
        active_client_context: contextvars.ContextVar[str | None],
        active_user_id_context: contextvars.ContextVar[int],
    ) -> None:
        _ = config
        if active_client_context is None:
            raise ValidationError("active_client_context is required for MCP tool sessions.")
        if active_user_id_context is None:
            raise ValidationError("active_user_id_context is required for MCP tool sessions.")
        self._active_client_context = active_client_context
        self._active_user_id_context = active_user_id_context
        self.workspace_states: dict[str, ToolWorkspaceState] = {}
        self.shell_sessions: dict[int, ShellSession] = {}
        self.shell_transcripts: dict[int, ShellTranscriptProtocol] = {}
        self.pending_terminal_close_sessions: dict[str, ShellSession] = {}
        self.next_session_id = 1

    def current_owner_key(self) -> str:
        value = self._active_client_context.get()
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "default"

    def current_user_id(self) -> int:
        return self._active_user_id_context.get()

    def require_workspace_path(self, owner_key: str | None = None) -> str:
        state = self.get_or_create_workspace_state(owner_key)
        value = state.workspace_path
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("workspace_path is not configured for MCP tool execution.")
        return value

    def prune_workspace_states(self) -> None:
        prune_workspace_states(self)

    def get_or_create_workspace_state(self, owner_key: str | None = None) -> ToolWorkspaceState:
        return get_or_create_workspace_state(self, owner_key)

    def set_workspace_path(
        self,
        workspace_path: str,
        owner_key: str | None = None,
    ) -> ToolWorkspaceState:
        return set_workspace_path(self, workspace_path, owner_key)

    def prune_shell_sessions(self) -> None:
        prune_shell_sessions(self)

    def create_shell_session(
        self,
        terminal_session_id: str,
        owner_key: str | None = None,
    ) -> ShellSession:
        return create_shell_session(self, terminal_session_id, owner_key)

    def get_shell_session(self, session_id: int) -> ShellSession | None:
        return get_shell_session(self, session_id)

    def close_shell_session(self, session_id: int) -> ShellSession | None:
        return close_shell_session(self, session_id)

    def close_shell_session_and_queue_terminal_close(self, session_id: int) -> ShellSession | None:
        return close_shell_session_and_queue_terminal_close(self, session_id)

    def list_shell_sessions_for_owner(self, owner_key: str | None = None) -> list[ShellSession]:
        return list_shell_sessions_for_owner(self, owner_key)

    def list_shell_sessions_for_user(self, user_id: int) -> list[ShellSession]:
        return list_shell_sessions_for_user(self, user_id)

    def append_shell_output(self, session_id: int, data: bytes) -> None:
        append_shell_output(self, session_id, data)

    def append_shell_transcript_output(self, session_id: int, data: bytes) -> None:
        append_shell_transcript_output(self, session_id, data)

    def create_shell_transcript(self, session_id: int, transcript_root: str) -> None:
        create_shell_transcript(self, session_id, transcript_root)

    def remove_shell_transcript(self, session_id: int) -> None:
        remove_shell_transcript(self, session_id)

    def read_shell_transcript_incremental(self, session_id: int, limit: int) -> JSONDict:
        return read_shell_transcript_incremental(self, session_id, limit)

    def snapshot_shell_transcript_page(self, session_id: int, limit: int) -> JSONDict:
        return snapshot_shell_transcript_page(self, session_id, limit)

    def read_shell_transcript_lines(
        self,
        session_id: int,
        offset: int,
        limit: int,
        from_end: bool,
    ) -> JSONDict:
        return read_shell_transcript_lines(self, session_id, offset, limit, from_end)

    def search_shell_transcript(
        self,
        session_id: int,
        query: str,
        offset: int,
        limit: int,
        case_sensitive: bool,
    ) -> JSONDict:
        return search_shell_transcript(self, session_id, query, offset, limit, case_sensitive)

    def mark_shell_exit(self, session_id: int, exit_code: int) -> None:
        mark_shell_exit(self, session_id, exit_code)

    def peek_shell_session_exit(self, session_id: int) -> tuple[bool, int | None]:
        return peek_shell_session_exit(self, session_id)

    def requeue_shell_session_for_terminal_close(self, session: ShellSession) -> None:
        requeue_shell_session_for_terminal_close(self, session)

    def drain_shell_output(self, session_id: int, max_chars: int) -> str:
        return drain_shell_output(self, session_id, max_chars)

    def snapshot_shell_output(self, session_id: int, max_chars: int) -> str:
        return snapshot_shell_output(self, session_id, max_chars)

    def pop_shell_sessions_pending_terminal_close(self) -> list[ShellSession]:
        return pop_shell_sessions_pending_terminal_close(self)
