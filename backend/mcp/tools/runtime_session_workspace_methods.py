"""SoAI - MCP runtime files root methods [backend/mcp/tools/runtime_session_workspace_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from core.files.workspace_path import resolve_existing_workspace_directory
from core.mcp.protocols_main import MCPToolRuntimeSessionWorkspaceStoreProtocol
from mcp.tools.runtime_types import ToolWorkspaceState

__all__ = (
    "get_or_create_workspace_state",
    "prune_workspace_states",
    "set_workspace_path",
    "touch_workspace_state",
)


def touch_workspace_state(state: ToolWorkspaceState) -> None:
    state.last_touched_monotonic = time.monotonic()


def prune_workspace_states(self: MCPToolRuntimeSessionWorkspaceStoreProtocol) -> None:
    now = time.monotonic()
    expired_owner_keys: list[str] = []
    for owner_key, entry in self.workspace_states.items():
        if (now - entry.last_touched_monotonic) >= self.WORKSPACE_IDLE_TTL_SEC:
            expired_owner_keys.append(owner_key)
    for owner_key in expired_owner_keys:
        self.workspace_states.pop(owner_key, None)
    entry_count = len(self.workspace_states)
    if entry_count <= self.WORKSPACE_MAX_PER_PROCESS:
        return
    least_recently_touched = sorted(
        self.workspace_states.items(),
        key=lambda item: item[1].last_touched_monotonic,
    )
    for owner_key, _entry in least_recently_touched:
        if entry_count <= self.WORKSPACE_MAX_PER_PROCESS:
            break
        self.workspace_states.pop(owner_key, None)
        entry_count -= 1


def get_or_create_workspace_state(
    self: MCPToolRuntimeSessionWorkspaceStoreProtocol,
    owner_key: str | None = None,
) -> ToolWorkspaceState:
    resolved_owner = (
        owner_key.strip()
        if isinstance(owner_key, str) and owner_key.strip()
        else self.current_owner_key()
    )
    self.prune_workspace_states()
    existing = self.workspace_states.get(resolved_owner)
    if existing is not None:
        touch_workspace_state(existing)
        return existing
    state = ToolWorkspaceState(workspace_path=None)
    self.workspace_states[resolved_owner] = state
    touch_workspace_state(state)
    self.prune_workspace_states()
    return state


def set_workspace_path(
    self: MCPToolRuntimeSessionWorkspaceStoreProtocol,
    workspace_path: str,
    owner_key: str | None = None,
) -> ToolWorkspaceState:
    resolved = resolve_existing_workspace_directory(workspace_path)
    state = self.get_or_create_workspace_state(owner_key)
    state.workspace_path = resolved
    touch_workspace_state(state)
    return state
