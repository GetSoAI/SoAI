"""SoAI - MCP server orchestration and JSON-RPC request dispatch [backend/mcp/server/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from re import Pattern
from typing import TYPE_CHECKING

from core.concurrency.task_groups import ManagedTaskGroup
from core.errors.exceptions import StateError
from core.mcp.protocols_main import MCPWebFetcherProtocol
from core.tasks.protocols import TaskFinalizerTrackerProtocol
from core.types.json import JSONDict, JSONValue
from mcp.server.dependencies import MCPServerDependencies
from mcp.server.public_operations import MCPServerOperations
from mcp.server.state import MCPServerState

if TYPE_CHECKING:
    from core.mcp.protocols_main import (
        MCPRegistrationProtocol,
        MCPRemoteProtocol,
        MCPSearchApiKeysProtocol,
        MCPSearchProtocol,
    )
    from core.mcp.protocols_runtime import (
        MCPContextProtocol,
        MCPPaginationProtocol,
        MCPSessionProtocol,
        MCPStreamingProtocol,
    )
    from core.tasks.protocols import TaskCancellationBinderProtocol
    from core.tasks.service_lifecycle import ServiceLifecycle
    from mcp.registry.internal_protocols import MCPTaskServiceProtocol
    from mcp.server.handlers.host_mode_client import MCPHostModeClient
    from mcp.server.handlers.lifecycle_manager import MCPLifecycleManager
    from mcp.server.handlers.notification_service import MCPNotificationService
    from mcp.server.runtime_bundle import MCPServerRuntimeBundle
    from mcp.tools.service import MCPUtilityTools

__all__ = ("MCPServer",)

LOGGER_NAME = "SoAI.mcp.server.service"


class MCPServer(MCPServerOperations):
    _lifecycle: ServiceLifecycle | None
    _cancellation_binder: TaskCancellationBinderProtocol | None
    _session: MCPSessionProtocol | None
    _streaming: MCPStreamingProtocol | None
    _notification: MCPNotificationService | None
    _context: MCPContextProtocol | None
    _task: MCPTaskServiceProtocol | None
    _search: MCPSearchProtocol | None
    _search_api_keys: MCPSearchApiKeysProtocol | None
    _registration: MCPRegistrationProtocol | None
    _host_mode: MCPHostModeClient | None
    _pagination: MCPPaginationProtocol | None
    allowed_origins: list[str]
    host_sampling_default_model: str | None
    finalizer_tracker: TaskFinalizerTrackerProtocol | None
    web_fetcher: MCPWebFetcherProtocol | None
    utility_tools_instance: MCPUtilityTools | None
    lifecycle_manager: MCPLifecycleManager | None

    @property
    def mcp_remote(self) -> MCPRemoteProtocol:
        return self._mcp_remote

    @property
    def utility_tools(self) -> MCPUtilityTools:
        tools = self.utility_tools_instance
        if tools is None:
            raise StateError("MCPServer runtime bundle is not attached.")
        return tools

    def _require_runtime_attachment[T](self, value: T | None) -> T:
        if value is None:
            raise StateError("MCPServer runtime bundle is not attached.")
        return value

    @property
    def lifecycle(self) -> ServiceLifecycle:
        return self._require_runtime_attachment(self._lifecycle)

    @property
    def cancellation_binder(self) -> TaskCancellationBinderProtocol:
        return self._require_runtime_attachment(self._cancellation_binder)

    @property
    def session(self) -> MCPSessionProtocol:
        return self._require_runtime_attachment(self._session)

    @property
    def streaming(self) -> MCPStreamingProtocol:
        return self._require_runtime_attachment(self._streaming)

    @property
    def notification(self) -> MCPNotificationService:
        return self._require_runtime_attachment(self._notification)

    @property
    def context(self) -> MCPContextProtocol:
        return self._require_runtime_attachment(self._context)

    @property
    def task(self) -> MCPTaskServiceProtocol:
        return self._require_runtime_attachment(self._task)

    @property
    def search(self) -> MCPSearchProtocol:
        return self._require_runtime_attachment(self._search)

    @property
    def search_api_keys(self) -> MCPSearchApiKeysProtocol:
        return self._require_runtime_attachment(self._search_api_keys)

    @property
    def registration(self) -> MCPRegistrationProtocol:
        return self._require_runtime_attachment(self._registration)

    @property
    def host_mode(self) -> MCPHostModeClient:
        return self._require_runtime_attachment(self._host_mode)

    @property
    def pagination(self) -> MCPPaginationProtocol:
        return self._require_runtime_attachment(self._pagination)

    @property
    def core_tool_handlers(
        self,
    ) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]]:
        return self._core_tool_handlers

    def attach_runtime(self, runtime_bundle: MCPServerRuntimeBundle) -> None:
        runtime_config = runtime_bundle.runtime_config
        components = runtime_bundle.components
        self._lifecycle = runtime_bundle.lifecycle
        self.shutdown_event = runtime_bundle.shutdown_event
        self._cancellation_binder = runtime_bundle.cancellation_binder
        self.finalizer_tracker = runtime_bundle.finalizer_tracker
        self.background_tasks = runtime_bundle.background_tasks
        self.web_fetcher = runtime_bundle.web_fetcher
        self.state = runtime_bundle.state
        self._search = runtime_bundle.search
        self._search_api_keys = runtime_bundle.search_api_keys
        self.utility_tools_instance = runtime_bundle.utility_tools
        self.pending_server_requests = self.state.task.pending_server_requests
        self.pending_server_requests_lock = self.state.task.pending_server_requests_lock
        self.task_method_map = self.state.task.task_method_map
        self.allowed_origins = list(runtime_config.allowed_origins)
        self.enabled = bool(runtime_config.enabled)
        self.host_mode_enabled = bool(runtime_config.enabled and runtime_config.host_mode_enabled)
        self.server_mode_enabled = bool(
            runtime_config.enabled and runtime_config.server_mode_enabled
        )
        self.tasks_enabled = bool(runtime_config.tasks_enabled)
        self.host_sampling_default_model = runtime_config.host_sampling_default_model
        self.tasks_proxy_timeout_sec = float(runtime_config.tasks_proxy_timeout_sec)
        self.tasks_tool_timeout_sec = float(runtime_config.tasks_tool_timeout_sec)
        self.list_changed_enabled = bool(runtime_config.list_changed_enabled)
        self._session = components.session
        self._streaming = components.streaming
        self._notification = components.notification
        self._pagination = components.pagination
        self._context = components.context
        self._host_mode = components.host_mode
        self._registration = components.registration
        self._task = components.task
        self.lifecycle_manager = components.lifecycle
        self.registered_resources = self.state.registration.registered_resources
        self.resource_subscriptions_lock = self.state.registration.resource_subscriptions_lock
        self.resource_subscriptions = self.state.registration.resource_subscriptions

    def __init__(self, deps: MCPServerDependencies) -> None:
        self.config = deps.config
        self.licensing_status = deps.licensing_status
        self.database_files = deps.database_files
        self.database_users = deps.database_users
        self.database_conversations = deps.database_conversations
        self.database_prompts = deps.database_prompts
        self.database_plugins = deps.database_plugins
        self.event_bus = deps.event_bus
        self.model_resolution_service = deps.model_resolution_service
        self.model_information_service = deps.model_information_service
        self.metrics_manager = deps.metrics_manager
        self.connection_registry = deps.connection_registry
        self._mcp_remote = deps.mcp_remote
        self.external_accounts = deps.external_accounts
        self.mail_account_queries = deps.mail_account_queries
        self.calendar_account_queries = deps.calendar_account_queries
        self.mail = deps.mail
        self.calendar = deps.calendar
        self.http_client = deps.http_client
        self.task_registry = deps.task_registry
        self._task_registry_queries = deps.task_registry_queries
        self._lifecycle = None
        self._cancellation_binder = None
        self._session = None
        self._streaming = None
        self._notification = None
        self._context = None
        self._task = None
        self._search = None
        self._search_api_keys = None
        self._registration = None
        self._host_mode = None
        self._pagination = None
        self.state = MCPServerState()
        self.pending_server_requests = self.state.task.pending_server_requests
        self.pending_server_requests_lock = self.state.task.pending_server_requests_lock
        self.task_method_map = self.state.task.task_method_map
        self.allowed_origins = []
        self.enabled = False
        self.host_mode_enabled = False
        self.server_mode_enabled = False
        self.tasks_enabled = False
        self.host_sampling_default_model = None
        self.tasks_proxy_timeout_sec = 0.0
        self.tasks_tool_timeout_sec = 0.0
        self.list_changed_enabled = False
        self._core_tool_handlers: dict[
            str,
            Callable[[JSONDict], Awaitable[JSONValue] | JSONValue],
        ] = {}
        self.registered_resources = self.state.registration.registered_resources
        self.resource_subscriptions_lock = self.state.registration.resource_subscriptions_lock
        self.resource_subscriptions = self.state.registration.resource_subscriptions
        self.shutdown_event = asyncio.Event()
        self.finalizer_tracker = None
        self.background_tasks = ManagedTaskGroup(label="mcp-server")
        self.web_fetcher = None
        self.utility_tools_instance = None
        self.lifecycle_manager = None

    @property
    def server_mode_active(self) -> bool:
        return bool(self.state.server_mode_active)

    @property
    def registered_tools_count(self) -> int:
        return len(self.state.registration.registered_tools)

    @property
    def registered_resources_count(self) -> int:
        return len(self.state.registration.registered_resources)

    @property
    def registered_prompts_count(self) -> int:
        return len(self.state.registration.registered_prompts)

    @property
    def task_proxy_timeout_seconds(self) -> float | None:
        if self.tasks_proxy_timeout_sec <= 0:
            return None
        return float(self.tasks_proxy_timeout_sec)

    @property
    def rag_resource_patterns(self) -> dict[str, Pattern[str]]:
        return self.state.rag_resource_patterns
