"""SoAI - Core runtime lifecycle protocols [backend/core/runtime/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Protocol, override

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.applications import Starlette
    from starlette.datastructures import URL, Address, Headers, State

    from core.database.vacuum_result import DatabaseVacuumStartupResult
    from core.orchestrator.types import MCPToolContext
    from core.rate_limiting.moving_window import MovingWindowRateLimiter
    from core.runtime.api_endpoint import RuntimeApiEndpoint
    from core.state.access import AccessAction
    from core.state.protocols import (
        RestartStateManagerProtocol,
        SystemRestartRequesterProtocol,
    )
    from core.system.protocols import ManagedProcessProtocol

__all__ = (
    "ConnectionProtocol",
    "ProxyHeadersAppProtocol",
    "ProxyHeadersStateProtocol",
    "RequestContextProtocol",
    "RequestOwnershipContextProtocol",
    "RequestProtocol",
    "RuntimeApiEndpointViewProtocol",
    "RuntimeFlagsMutationProtocol",
    "RuntimeFlagsViewProtocol",
    "RuntimeHealthViewProtocol",
    "RuntimePidLockProtocol",
    "RuntimePlatformViewProtocol",
    "RuntimeRepairPlaneViewProtocol",
    "RuntimeStateStoreProtocol",
)


class RuntimeFlagsViewProtocol(Protocol):
    @property
    def host_system_actions_disabled(self) -> bool: ...
    @property
    def hardware_mutation_disabled(self) -> bool: ...
    @property
    def offline_mode(self) -> bool: ...
    @property
    def block_private_network_egress(self) -> bool: ...
    @property
    def dns_validation_timeout_sec(self) -> float: ...
    @property
    def host_management_available(self) -> bool: ...
    @property
    def host_management_enabled(self) -> bool: ...


class RuntimeFlagsMutationProtocol(RuntimeFlagsViewProtocol, Protocol):
    def update_runtime_policy(
        self,
        *,
        host_system_actions_disabled: bool,
        hardware_mutation_disabled: bool,
        offline_mode: bool,
        block_private_network_egress: bool,
        dns_validation_timeout_sec: float,
        host_management_available: bool,
    ) -> None: ...


class RequestOwnershipContextProtocol(Protocol):
    trace_id: str
    client_ip: str | None
    user_id: int
    cancellation_id: str
    agent_mode: str | None
    mcp_tool_context: MCPToolContext | None


class RequestContextProtocol(Protocol):
    trace_id: str
    cancellation_id: str
    client_ip: str | None
    user_id: int
    timestamp: float
    task_id: str | None
    mcp_tool_context: MCPToolContext | None
    interactive_tool_approval: bool
    agent_mode: str | None
    agent_turn_id: str | None
    agent_turn_scope: str | None
    agent_turn_execution_token: str | None
    agent_iteration_index: int | None
    agent_parent_turn_id: str | None
    agent_parent_tool_call_id: str | None
    agent_parent_iteration_index: int | None
    agent_display_name: str | None
    agent_requested_model: str | None
    agent_owner_task_id: str | None
    agent_workspace_path: str | None
    access_actions: frozenset[AccessAction]


class RuntimePlatformViewProtocol(Protocol):
    @property
    def os_name(self) -> str: ...
    @property
    def architecture(self) -> str: ...
    @property
    def python_version(self) -> str: ...
    @property
    def is_windows(self) -> bool: ...
    @property
    def is_linux(self) -> bool: ...
    @property
    def is_macos(self) -> bool: ...


class RuntimePidLockProtocol(Protocol):
    @property
    def lock_file(self) -> str: ...

    def release(self) -> None: ...


class RuntimeApiEndpointViewProtocol(Protocol):
    @property
    def runtime_api_endpoint(self) -> RuntimeApiEndpoint | None: ...


class RuntimeRepairPlaneViewProtocol(Protocol):
    @property
    def repair_plane(self) -> bool: ...

    @property
    def restart_pending(self) -> asyncio.Event: ...


class RuntimeHealthViewProtocol(
    RuntimeApiEndpointViewProtocol,
    RuntimeRepairPlaneViewProtocol,
    Protocol,
):
    @property
    def degraded_mode(self) -> bool: ...

    @property
    def database_maintenance(self) -> DatabaseVacuumStartupResult: ...


class RuntimeStateStoreProtocol(RuntimeHealthViewProtocol, Protocol):
    @property
    def startup_time(self) -> float: ...

    @property
    def system_stop_event(self) -> asyncio.Event: ...

    @property
    @override
    def restart_pending(self) -> asyncio.Event: ...

    @property
    def startup_ready_event(self) -> asyncio.Event: ...

    @property
    def shutdown_event(self) -> asyncio.Event: ...

    @property
    def restart_state_manager(self) -> RestartStateManagerProtocol | None: ...

    @property
    def system_restart_requester(self) -> SystemRestartRequesterProtocol | None: ...

    @property
    def hardware_manager_available(self) -> bool: ...

    @property
    @override
    def repair_plane(self) -> bool: ...

    @property
    def webui_available(self) -> bool: ...

    @property
    def tls_user_supplied(self) -> bool: ...

    @property
    def is_shutting_down(self) -> bool: ...

    @property
    def restart_requested(self) -> bool: ...

    @property
    def manual_shutdown_requested(self) -> bool: ...

    @property
    def exit_code(self) -> int: ...

    @property
    def critical_shutdown_reason(self) -> str | None: ...

    @property
    def pid_lock(self) -> RuntimePidLockProtocol | None: ...

    @property
    def async_loop(self) -> asyncio.AbstractEventLoop | None: ...

    @property
    def prune_tokens_task(self) -> asyncio.Task[None] | None: ...

    @property
    def fastapi_app(self) -> FastAPI | None: ...

    @property
    def request_rate_limiter(self) -> MovingWindowRateLimiter | None: ...

    @property
    def transferred_processes(self) -> tuple[ManagedProcessProtocol, ...]: ...

    def set_restart_state_manager(
        self,
        restart_state_manager: RestartStateManagerProtocol,
    ) -> None: ...

    def set_system_restart_requester(
        self,
        system_restart_requester: SystemRestartRequesterProtocol,
    ) -> None: ...

    def set_restart_required(self) -> None: ...

    def set_server_runtime(
        self,
        *,
        runtime_api_endpoint: RuntimeApiEndpoint,
        tls_user_supplied: bool,
        fastapi_app: FastAPI | None = None,
        request_rate_limiter: MovingWindowRateLimiter | None = None,
    ) -> None: ...

    def set_webui_available(self, available: bool) -> None: ...

    def set_degraded_mode(self, enabled: bool) -> None: ...

    def set_database_maintenance(self, result: DatabaseVacuumStartupResult) -> None: ...

    def set_repair_plane(self, enabled: bool) -> None: ...

    def set_startup_ready(self) -> bool: ...

    def set_critical_shutdown(self, reason: str, exit_code: int) -> None: ...

    def set_manual_shutdown_requested(self) -> None: ...

    def begin_shutdown(self) -> bool: ...

    def set_system_stop(self) -> None: ...

    def set_shutdown_requested(self) -> None: ...

    def set_pid_lock(self, pid_lock: RuntimePidLockProtocol | None) -> None: ...

    def set_prune_tokens_task(self, task: asyncio.Task[None] | None) -> None: ...

    def transfer_process_ownership(self, process_handle: ManagedProcessProtocol) -> None: ...


class ConnectionProtocol(Protocol):
    @property
    def app(self) -> Starlette: ...

    @property
    def state(self) -> State: ...


class ProxyHeadersStateProtocol(Protocol):
    proxy_headers_enabled: bool
    trusted_proxy_networks: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network]


class ProxyHeadersAppProtocol(Protocol):
    state: ProxyHeadersStateProtocol


class RequestProtocol(Protocol):
    @property
    def method(self) -> str: ...

    @property
    def url(self) -> URL: ...

    @property
    def scope(self) -> Mapping[str, str | int | float | bool | bytes | None]: ...

    @property
    def headers(self) -> Headers: ...

    @property
    def cookies(self) -> Mapping[str, str]: ...

    @property
    def client(self) -> Address | None: ...

    @property
    def app(self) -> Starlette: ...

    @property
    def state(self) -> State: ...
