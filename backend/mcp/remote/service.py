"""SoAI - MCP host-mode client with remote server connections [backend/mcp/remote/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from core.logging.trace import get_logger
from core.mcp.protocol_versions import MCP_PROTOCOL_VERSION
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.tasks.service_lifecycle import initialize_managed_task_group
from mcp.host.internal_protocols import MCPServerHostProtocol
from mcp.remote.dependencies import (
    MCPConnectionManagerDependencies,
    MCPRemoteDependencies,
)
from mcp.remote.public_operations import MCPRemoteOperations
from mcp.server.runtime_config import build_runtime_config

if TYPE_CHECKING:
    import httpx2
    from cryptography.fernet import Fernet

    from core.concurrency.task_groups import ManagedTaskGroup
    from core.mcp.protocols_storage import DatabaseMCPProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.remote.internal_protocols import (
        MCPConnectionManagerProtocol,
        MCPElicitationStateProtocol,
        MCPHostRootsStateProtocol,
    )

__all__ = ("MCPRemote",)

LOGGER_NAME = "SoAI.mcp.remote.service"


class MCPRemote(MCPRemoteOperations):
    HOST_ROOTS_SETTING_KEY: ClassVar[str] = "mcp_host_roots"
    PENDING_URL_ELICITATIONS_SETTING_KEY: ClassVar[str] = "mcp_pending_url_elicitations"

    def __init__(self, deps: MCPRemoteDependencies) -> None:
        logger = get_logger(LOGGER_NAME)
        self._deps = deps
        self.config = deps.config
        self._db_mcp = deps.database_mcp
        self._db_plugins = deps.database_plugins
        self._fernet = deps.database_plugins.fernet
        self.event_bus = deps.event_bus
        self._http_client = deps.http_client
        self.server: MCPServerHostProtocol | None = None
        self.connection_registry = deps.connection_registry
        self.connections = self.connection_registry.connections
        remote_config = build_runtime_config(deps.config)
        self._enabled = remote_config.enabled
        self._host_mode_enabled = remote_config.host_mode_enabled
        self._host_roots_list_changed_enabled = remote_config.host_roots_list_changed_enabled
        self.host_elicitation_enabled = remote_config.host_elicitation_enabled
        self._auto_connect_on_startup = remote_config.auto_connect_on_startup
        self._tasks_enabled = remote_config.tasks_enabled
        self.host_sampling_enabled = remote_config.host_sampling_enabled
        self._max_reconnect_attempts = remote_config.max_reconnect_attempts
        self._reconnect_delay = remote_config.reconnect_delay
        self._oauth_refresh_skew_ms = remote_config.oauth_refresh_skew_ms
        self._public_origin = remote_config.public_origin
        self._oauth_state_token_ttl_ms = remote_config.oauth_state_token_ttl_ms
        self._host_roots: list[JSONValue] = list(remote_config.host_roots)
        (
            self.lifecycle,
            self._shutdown_event,
            self._cancellation_binder,
            self._finalizer_tracker,
            self._background_tasks,
        ) = initialize_managed_task_group(
            "mcp remote tasks",
            logger=logger,
            error_message="MCP remote lifecycle did not initialize a managed task group.",
            cancellation_binder=deps.cancellation_binder,
            finalizer_tracker=deps.finalizer_tracker,
            operation_name="mcp.remote.background_task_completion",
        )
        self._metrics = deps.metrics_manager
        self._host_roots_state: MCPHostRootsStateProtocol | None = None
        self._elicitation_state: MCPElicitationStateProtocol | None = None
        connection_manager_deps = MCPConnectionManagerDependencies(
            connection_registry=deps.connection_registry,
            db_mcp=deps.database_mcp,
            event_bus=deps.event_bus,
            http_client=deps.http_client,
            runtime_flags=deps.runtime_flags,
            shutdown_event=self._shutdown_event,
            metrics_manager=deps.metrics_manager,
            decrypt_api_key=self.decrypt_mcp_api_key,
            build_client_capabilities=self.build_client_capabilities,
            track_background_task=self.track_background_task,
            send_host_mode_message=self.send_host_mode_message_for_connection,
            host_context=self,
            max_reconnect_attempts=self._max_reconnect_attempts,
            reconnect_delay=self._reconnect_delay,
            protocol_version=MCP_PROTOCOL_VERSION,
            oauth_refresh_skew_ms=int(self._oauth_refresh_skew_ms),
        )
        self._connection_manager = deps.connection_manager_builder(connection_manager_deps)
        self._tool_catalog_cache_key: tuple[tuple[str, int, int], ...] | None = None
        self._tool_catalog_cache_snapshot: tuple[JSONDict, ...] = ()

    @property
    def tool_catalog_cache_key(self) -> tuple[tuple[str, int, int], ...] | None:
        return self._tool_catalog_cache_key

    @tool_catalog_cache_key.setter
    def tool_catalog_cache_key(self, value: tuple[tuple[str, int, int], ...] | None) -> None:
        self._tool_catalog_cache_key = value

    @property
    def tool_catalog_cache_snapshot(self) -> tuple[JSONDict, ...]:
        return self._tool_catalog_cache_snapshot

    @tool_catalog_cache_snapshot.setter
    def tool_catalog_cache_snapshot(self, value: tuple[JSONDict, ...]) -> None:
        self._tool_catalog_cache_snapshot = value

    @property
    def db_plugins(self) -> DatabasePluginsProtocol:
        return self._db_plugins

    @property
    def db_mcp(self) -> DatabaseMCPProtocol:
        return self._db_mcp

    @property
    def fernet(self) -> tuple[Fernet, ...]:
        return self._fernet

    @property
    def http_client(self) -> httpx2.AsyncClient:
        return self._http_client

    @property
    def runtime_flags(self) -> RuntimeFlagsViewProtocol:
        return self._deps.runtime_flags

    @property
    def connection_manager(self) -> MCPConnectionManagerProtocol:
        return self._connection_manager

    @property
    def background_tasks(self) -> ManagedTaskGroup:
        return self._background_tasks

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def host_mode_enabled(self) -> bool:
        return self._host_mode_enabled

    @property
    def host_roots_list_changed_enabled(self) -> bool:
        return self._host_roots_list_changed_enabled

    @property
    def host_roots(self) -> list[JSONValue]:
        return list(self._host_roots)

    @property
    def public_origin(self) -> str:
        return str(self._public_origin or "")

    @property
    def oauth_state_token_ttl_ms(self) -> int:
        return int(self._oauth_state_token_ttl_ms)

    @property
    def host_roots_state(self) -> MCPHostRootsStateProtocol | None:
        return self._host_roots_state

    @host_roots_state.setter
    def host_roots_state(self, value: MCPHostRootsStateProtocol | None) -> None:
        self._host_roots_state = value

    @property
    def elicitation_state(self) -> MCPElicitationStateProtocol | None:
        return self._elicitation_state

    @elicitation_state.setter
    def elicitation_state(self, value: MCPElicitationStateProtocol | None) -> None:
        self._elicitation_state = value

    @property
    def auto_connect_on_startup(self) -> bool:
        return self._auto_connect_on_startup

    @property
    def tasks_enabled(self) -> bool:
        return self._tasks_enabled
