"""SoAI - MCP remote dependencies [backend/mcp/remote/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.di.validation import require_dependencies
from core.runtime.protocols import RuntimeFlagsViewProtocol
from mcp.remote.internal_protocols import MCPConnectionManagerProtocol

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.mcp.protocols_storage import DatabaseMCPProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict
    from mcp.host.internal_protocols import MCPHostContextProtocol
    from mcp.protocol.connection_state import MCPServerConnection
    from mcp.registry.internal_protocols import MCPConnectionRegistryProtocol

__all__ = (
    "MCPConnectionManagerDependencies",
    "MCPRemoteDependencies",
)


@dataclass(frozen=True, slots=True)
class MCPRemoteDependencies:
    config: ConfigProtocol
    database_mcp: DatabaseMCPProtocol
    database_plugins: DatabasePluginsProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    event_bus: EventBusProtocol
    http_client: httpx2.AsyncClient
    connection_registry: MCPConnectionRegistryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    metrics_manager: MetricsManagerProtocol
    connection_manager_builder: Callable[
        [MCPConnectionManagerDependencies],
        MCPConnectionManagerProtocol,
    ]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPRemoteDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            connection_manager_builder=self.connection_manager_builder,
            connection_registry=self.connection_registry,
            database_mcp=self.database_mcp,
            database_plugins=self.database_plugins,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            http_client=self.http_client,
            metrics_manager=self.metrics_manager,
            runtime_flags=self.runtime_flags,
        )


@dataclass(frozen=True, slots=True)
class MCPConnectionManagerDependencies:
    connection_registry: MCPConnectionRegistryProtocol
    db_mcp: DatabaseMCPProtocol
    event_bus: EventBusProtocol
    http_client: httpx2.AsyncClient
    runtime_flags: RuntimeFlagsViewProtocol
    shutdown_event: asyncio.Event
    metrics_manager: MetricsManagerProtocol
    decrypt_api_key: Callable[[str], str | None]
    build_client_capabilities: Callable[[], JSONDict]
    track_background_task: Callable[[asyncio.Task[None]], None]
    send_host_mode_message: Callable[[MCPServerConnection, JSONDict], Awaitable[None]]
    host_context: MCPHostContextProtocol
    max_reconnect_attempts: int
    reconnect_delay: float
    protocol_version: str
    oauth_refresh_skew_ms: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPConnectionManagerDependencies",
            build_client_capabilities=self.build_client_capabilities,
            connection_registry=self.connection_registry,
            db_mcp=self.db_mcp,
            decrypt_api_key=self.decrypt_api_key,
            event_bus=self.event_bus,
            host_context=self.host_context,
            http_client=self.http_client,
            max_reconnect_attempts=self.max_reconnect_attempts,
            metrics_manager=self.metrics_manager,
            protocol_version=self.protocol_version,
            reconnect_delay=self.reconnect_delay,
            runtime_flags=self.runtime_flags,
            send_host_mode_message=self.send_host_mode_message,
            shutdown_event=self.shutdown_event,
            track_background_task=self.track_background_task,
            oauth_refresh_skew_ms=self.oauth_refresh_skew_ms,
        )
