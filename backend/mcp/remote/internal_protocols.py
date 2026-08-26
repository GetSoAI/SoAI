"""SoAI - MCP remote internal protocols [backend/mcp/remote/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ClassVar, Protocol, override

from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.types import MCPServerConfig, MCPServerStatus
from mcp.registry.internal_protocols import MCPConnectionRegistryProtocol

if TYPE_CHECKING:
    import httpx2
    from cryptography.fernet import Fernet

    from core.concurrency.task_groups import ManagedTaskGroup
    from core.events.protocols import EventBusProtocol
    from core.mcp.protocols_storage import DatabaseMCPProtocol
    from core.metrics.protocols import MetricsRecorderProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.host.internal_protocols import MCPServerHostProtocol

__all__ = (
    "MCPConnectionManagerOperationsSurface",
    "MCPConnectionManagerProtocol",
    "MCPConnectionManagerRuntimeDepsSurface",
    "MCPElicitationStateProtocol",
    "MCPHostRootsStateProtocol",
    "MCPReconnectionHandlerProtocol",
    "MCPRemoteBackgroundTaskSurface",
    "MCPRemoteHostModeMessagingSurface",
    "MCPRemoteHostStateSurface",
    "MCPRemoteOAuthOperationsSurface",
    "MCPRemoteServiceOperationsSurface",
    "MCPRemoteToolCatalogSurface",
    "MCPTransportConnectorProtocol",
    "PersistSettingProtocol",
)


class PersistSettingProtocol(Protocol):
    def __call__(
        self,
        key: str,
        value: JSONValue,
    ) -> Awaitable[None]: ...


class MCPConnectionManagerProtocol(Protocol):
    @property
    def oauth_refresh_skew_ms(self) -> int: ...

    async def connect_to_server(self, config: MCPServerConfig) -> bool: ...

    async def disconnect_from_server(self, server_id: str) -> bool: ...

    async def disconnect_connection(
        self,
        connection: MCPServerConnection,
        *,
        server_id: str,
        reason: str,
    ) -> bool: ...

    async def update_server_status(
        self,
        server_id: str,
        status: MCPServerStatus,
        error: str | None = None,
    ) -> None: ...

    def build_http_headers(
        self,
        config: MCPServerConfig,
        protocol_version: str | None,
    ) -> dict[str, str]: ...

    async def cleanup_connection_resources(self, connection: MCPServerConnection) -> None: ...


class MCPTransportConnectorProtocol(Protocol):
    async def connect_stdio(self, connection: MCPServerConnection) -> bool: ...

    async def connect_streamable_http(self, connection: MCPServerConnection) -> bool: ...


class MCPReconnectionHandlerProtocol(Protocol):
    async def attempt_reconnection(self, connection: MCPServerConnection) -> bool: ...


class MCPConnectionManagerRuntimeDepsSurface(Protocol):
    @property
    def runtime_flags(self) -> RuntimeFlagsViewProtocol: ...


class MCPConnectionManagerOperationsSurface(MCPConnectionManagerProtocol, Protocol):
    @property
    def deps(self) -> MCPConnectionManagerRuntimeDepsSurface: ...

    @property
    def registry(self) -> MCPConnectionRegistryProtocol: ...

    @property
    def db_mcp(self) -> DatabaseMCPProtocol: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def http_client(self) -> httpx2.AsyncClient: ...

    @property
    def shutdown_event(self) -> asyncio.Event: ...

    @property
    def metrics(self) -> MetricsRecorderProtocol: ...

    @property
    def decrypt_api_key(self) -> Callable[[str], str | None]: ...

    @property
    def transport_connector(self) -> MCPTransportConnectorProtocol: ...

    @property
    def reconnection_handler(self) -> MCPReconnectionHandlerProtocol: ...

    async def connect_by_transport_type(self, connection: MCPServerConnection) -> bool: ...

    async def finalize_connection(
        self,
        config: MCPServerConfig,
        connection: MCPServerConnection,
        connected: bool,
    ) -> bool: ...


class MCPRemoteToolCatalogSurface(Protocol):
    @property
    def connection_registry(self) -> MCPConnectionRegistryProtocol: ...

    @property
    def tool_catalog_cache_key(self) -> tuple[tuple[str, int, int], ...] | None: ...

    @tool_catalog_cache_key.setter
    def tool_catalog_cache_key(self, value: tuple[tuple[str, int, int], ...] | None) -> None: ...

    @property
    def tool_catalog_cache_snapshot(self) -> tuple[JSONDict, ...]: ...

    @tool_catalog_cache_snapshot.setter
    def tool_catalog_cache_snapshot(self, value: tuple[JSONDict, ...]) -> None: ...


class MCPHostRootsStateProtocol(Protocol):
    def normalize(self, roots: list[JSONValue] | None = None) -> list[JSONDict]: ...

    async def set(self, roots: list[JSONValue]) -> list[JSONDict]: ...

    async def load_from_stored(self, stored_value: JSONValue) -> None: ...


class MCPElicitationStateProtocol(Protocol):
    async def record(self, server_id: str, elicitation_id: str, task_id: str) -> None: ...

    async def clear(self, client_id: str, elicitation_id: str) -> bool: ...

    async def clear_for_task(self, client_id: str, elicitation_id: str, task_id: str) -> bool: ...

    def load_from_stored(self, stored_value: JSONValue) -> None: ...


class MCPRemoteHostStateSurface(Protocol):
    connection_registry: MCPConnectionRegistryProtocol

    @property
    def db_plugins(self) -> DatabasePluginsProtocol: ...

    @property
    def host_roots_state(self) -> MCPHostRootsStateProtocol | None: ...

    @host_roots_state.setter
    def host_roots_state(self, value: MCPHostRootsStateProtocol | None) -> None: ...

    @property
    def elicitation_state(self) -> MCPElicitationStateProtocol | None: ...

    @elicitation_state.setter
    def elicitation_state(self, value: MCPElicitationStateProtocol | None) -> None: ...

    @property
    def host_roots_list_changed_enabled(self) -> bool: ...

    @property
    def host_roots(self) -> list[JSONValue]: ...

    @property
    def enabled(self) -> bool: ...

    @property
    def host_mode_enabled(self) -> bool: ...

    host_elicitation_enabled: bool

    @property
    def auto_connect_on_startup(self) -> bool: ...

    HOST_ROOTS_SETTING_KEY: ClassVar[str]
    PENDING_URL_ELICITATIONS_SETTING_KEY: ClassVar[str]

    def initialize_state_managers(self) -> None: ...

    async def send_host_mode_message_for_connection(
        self,
        connection: MCPServerConnection,
        message: JSONDict,
    ) -> None: ...

    async def auto_connect_servers(self) -> None: ...


class MCPRemoteBackgroundTaskSurface(Protocol):
    def track_background_task(self, task: asyncio.Task[None]) -> None: ...


class MCPRemoteHostModeMessagingSurface(Protocol):
    @property
    def connection_manager(self) -> MCPConnectionManagerProtocol: ...

    @property
    def db_mcp(self) -> DatabaseMCPProtocol: ...

    @property
    def http_client(self) -> httpx2.AsyncClient: ...

    @property
    def runtime_flags(self) -> RuntimeFlagsViewProtocol: ...

    def decrypt_mcp_api_key(self, encrypted: str) -> str | None: ...

    async def get_connected_server(self, server_id: str) -> MCPServerConnection: ...

    async def send_host_mode_message_for_connection(
        self,
        connection: MCPServerConnection,
        message: JSONDict,
    ) -> None: ...

    async def send_host_mode_request_for_connection(
        self,
        connection: MCPServerConnection,
        method: str,
        parameters: JSONDict,
    ) -> JSONValue | None: ...


class MCPRemoteOAuthOperationsSurface(Protocol):
    @property
    def db_mcp(self) -> DatabaseMCPProtocol: ...

    @property
    def connection_manager(self) -> MCPConnectionManagerProtocol: ...

    @property
    def runtime_flags(self) -> RuntimeFlagsViewProtocol: ...

    @property
    def http_client(self) -> httpx2.AsyncClient: ...

    @property
    def public_origin(self) -> str: ...

    @property
    def oauth_state_token_ttl_ms(self) -> int: ...

    @property
    def fernet(self) -> tuple[Fernet, ...]: ...

    def decrypt_mcp_api_key(self, encrypted: str) -> str | None: ...

    def build_client_capabilities(self) -> JSONDict: ...

    async def connect_to_server_by_id(self, server_id: str) -> bool: ...


class MCPRemoteServiceOperationsSurface(
    MCPRemoteBackgroundTaskSurface,
    MCPRemoteHostModeMessagingSurface,
    Protocol,
):
    server: MCPServerHostProtocol | None

    @property
    def connection_registry(self) -> MCPConnectionRegistryProtocol: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def background_tasks(self) -> ManagedTaskGroup: ...

    @property
    def host_sampling_enabled(self) -> bool: ...

    @property
    def host_elicitation_enabled(self) -> bool: ...

    @property
    @override
    def db_mcp(self) -> DatabaseMCPProtocol: ...

    @property
    def fernet(self) -> tuple[Fernet, ...]: ...

    @property
    def host_mode_enabled(self) -> bool: ...

    @property
    def host_roots_list_changed_enabled(self) -> bool: ...

    @property
    def tasks_enabled(self) -> bool: ...

    def build_client_capabilities(self) -> JSONDict: ...
