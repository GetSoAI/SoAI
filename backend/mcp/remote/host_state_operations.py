"""SoAI - MCP remote host state operations [backend/mcp/remote/host_state_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict, JSONValue, is_json_value
from mcp.remote.elicitation_state import MCPElicitationState
from mcp.remote.host_roots_state import MCPHostRootsState
from mcp.remote.internal_protocols import MCPRemoteHostStateSurface

__all__ = (
    "clear_pending_url_elicitation_for_task_method",
    "clear_pending_url_elicitation_method",
    "get_host_roots_method",
    "initialize_state_managers_method",
    "normalize_roots_method",
    "record_pending_url_elicitation_method",
    "set_host_roots_method",
    "start_method",
)


def initialize_state_managers_method(self: MCPRemoteHostStateSurface) -> None:
    db_plugins = self.db_plugins
    self.host_roots_state = MCPHostRootsState(
        connection_registry=self.connection_registry,
        send_message=self.send_host_mode_message_for_connection,
        persist_setting=db_plugins.set_system_setting,
        setting_key=self.HOST_ROOTS_SETTING_KEY,
        list_changed_enabled=self.host_roots_list_changed_enabled,
        initial_roots=self.host_roots,
    )
    self.elicitation_state = MCPElicitationState(
        persist_setting=db_plugins.set_system_setting,
        setting_key=self.PENDING_URL_ELICITATIONS_SETTING_KEY,
    )


def normalize_roots_method(
    self: MCPRemoteHostStateSurface,
    roots: list[JSONValue] | None = None,
) -> list[JSONDict]:
    host_roots_state = self.host_roots_state
    if host_roots_state is None:
        return []
    return host_roots_state.normalize(roots)


def get_host_roots_method(self: MCPRemoteHostStateSurface) -> list[JSONDict]:
    host_roots_state = self.host_roots_state
    if host_roots_state is None:
        return []
    return host_roots_state.normalize()


async def set_host_roots_method(
    self: MCPRemoteHostStateSurface,
    roots: list[JSONValue],
) -> list[JSONDict]:
    host_roots_state = self.host_roots_state
    if host_roots_state is None:
        return []
    return await host_roots_state.set(roots)


async def record_pending_url_elicitation_method(
    self: MCPRemoteHostStateSurface,
    server_id: str,
    elicitation_id: str,
    task_id: str,
) -> None:
    elicitation_state = self.elicitation_state
    if elicitation_state is not None:
        await elicitation_state.record(server_id, elicitation_id, task_id)


async def clear_pending_url_elicitation_method(
    self: MCPRemoteHostStateSurface,
    client_id: str,
    elicitation_id: str,
) -> bool:
    elicitation_state = self.elicitation_state
    if elicitation_state is None:
        return False
    return await elicitation_state.clear(client_id, elicitation_id)


async def clear_pending_url_elicitation_for_task_method(
    self: MCPRemoteHostStateSurface,
    client_id: str,
    elicitation_id: str,
    task_id: str,
) -> bool:
    elicitation_state = self.elicitation_state
    if elicitation_state is None:
        return False
    return await elicitation_state.clear_for_task(client_id, elicitation_id, task_id)


async def start_method(self: MCPRemoteHostStateSurface) -> None:
    if not self.enabled or not self.host_mode_enabled:
        return
    self.initialize_state_managers()
    db_plugins = self.db_plugins
    stored_roots = await db_plugins.get_system_setting(self.HOST_ROOTS_SETTING_KEY)
    stored_roots_value = stored_roots if is_json_value(stored_roots) else None
    host_roots_state = self.host_roots_state
    elicitation_state = self.elicitation_state
    if host_roots_state is not None:
        await host_roots_state.load_from_stored(stored_roots_value)
    if self.host_elicitation_enabled and elicitation_state is not None:
        stored_elicitations = await db_plugins.get_system_setting(
            self.PENDING_URL_ELICITATIONS_SETTING_KEY,
        )
        if is_json_value(stored_elicitations):
            elicitation_state.load_from_stored(stored_elicitations)
    if self.auto_connect_on_startup:
        await self.auto_connect_servers()
