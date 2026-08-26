"""SoAI - MCP registry internal protocols [backend/mcp/registry/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import weakref
from collections.abc import Awaitable, Callable
from re import Pattern
from typing import TYPE_CHECKING, Protocol, override

from core.mcp.protocols_runtime import MCPTaskProtocol
from core.tasks.enums import TaskStatus

if TYPE_CHECKING:
    from core.calendar.protocols import CalendarServiceProtocol
    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.licensing.protocols import LicensingStatusProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.mcp.protocols_main import MCPRegistrationProtocol
    from core.mcp.protocols_runtime import (
        MCPContextProtocol,
        MCPPaginationProtocol,
        MCPSessionProtocol,
    )
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols import ModelInformationServiceProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.prompts.protocols_database import DatabasePromptsProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskRegistryProtocol,
    )
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue
    from mcp.protocol.connection_state import MCPServerConnection
    from mcp.server.state import MCPServerPendingRequestKey, MCPServerState
    from mcp.tools.service import MCPUtilityTools

__all__ = (
    "MCPConnectionRegistryProtocol",
    "MCPHostModeClientProtocol",
    "MCPRegistryManagerProtocol",
    "MCPTaskHandlerManagerProtocol",
    "MCPTaskServiceProtocol",
)


class MCPConnectionRegistryProtocol(Protocol):
    connections: dict[str, MCPServerConnection]
    connections_lock: asyncio.Lock


class MCPHostModeClientProtocol(Protocol):
    def build_core_app_info(self) -> JSONDict: ...

    async def send_host_mode_request(
        self,
        server_id: str,
        method: str,
        parameters: JSONDict,
    ) -> JSONValue: ...


class MCPRegistryManagerProtocol(Protocol):
    @property
    def licensing_status(self) -> LicensingStatusProtocol: ...

    @property
    def state(self) -> MCPServerState: ...

    @property
    def pending_server_requests(
        self,
    ) -> dict[MCPServerPendingRequestKey, asyncio.Task[JSONValue]]: ...

    @property
    def pending_server_requests_lock(self) -> asyncio.Lock: ...

    @property
    def task_method_map(
        self,
    ) -> weakref.WeakKeyDictionary[asyncio.Task[JSONValue], str]: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def cancellation_binder(self) -> TaskCancellationBinderProtocol: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def config(self) -> ConfigProtocol: ...

    @property
    def database_files(self) -> DatabaseFilesProtocol: ...

    @property
    def database_prompts(self) -> DatabasePromptsProtocol: ...

    @property
    def database_plugins(self) -> DatabasePluginsProtocol: ...

    @property
    def list_changed_enabled(self) -> bool: ...

    @property
    def tasks_enabled(self) -> bool: ...

    @property
    def tasks_proxy_timeout_sec(self) -> float: ...

    @property
    def tasks_tool_timeout_sec(self) -> float: ...

    @property
    def enabled(self) -> bool: ...

    @property
    def registered_resources(
        self,
    ) -> dict[str, Callable[[], Awaitable[JSONDict]]]: ...

    @property
    def rag_resource_patterns(self) -> dict[str, Pattern[str]]: ...

    @property
    def resource_subscriptions_lock(self) -> asyncio.Lock: ...

    @property
    def resource_subscriptions(self) -> dict[str, set[str]]: ...

    @property
    def registration(self) -> MCPRegistrationProtocol: ...

    @property
    def pagination(self) -> MCPPaginationProtocol: ...

    @property
    def task(self) -> MCPTaskServiceProtocol: ...

    @property
    def connection_registry(self) -> MCPConnectionRegistryProtocol: ...

    @property
    def session(self) -> MCPSessionProtocol: ...

    @property
    def metrics_manager(self) -> MetricsManagerProtocol: ...

    @property
    def context(self) -> MCPContextProtocol: ...

    @property
    def utility_tools(self) -> MCPUtilityTools | None: ...

    @property
    def mail(self) -> MailServiceProtocol: ...

    @property
    def calendar(self) -> CalendarServiceProtocol: ...

    def track_background_task(self, task: asyncio.Task[None]) -> None: ...

    @property
    def host_mode(self) -> MCPHostModeClientProtocol: ...

    @property
    def model_information_service(
        self,
    ) -> ModelInformationServiceProtocol | None: ...


class MCPTaskHandlerManagerProtocol(Protocol):
    @property
    def state(self) -> MCPServerState: ...

    @property
    def tasks_enabled(self) -> bool: ...

    @property
    def pagination(self) -> MCPPaginationProtocol: ...

    @property
    def task(self) -> MCPTaskServiceProtocol: ...


class MCPTaskServiceProtocol(MCPTaskProtocol, Protocol):
    @override
    async def fail_task(self, task_id: str, code: int, message: str) -> None: ...

    @override
    async def cancel_task(self, task_id: str, reason: str) -> None: ...

    @override
    async def update_task_non_terminal_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str,
    ) -> None: ...

    @override
    async def complete_task(
        self,
        task_id: str,
        result: JSONDict,
        message: str | None = None,
    ) -> None: ...

    async def create_task(self, client_id: str, method: str, parameters: JSONDict) -> Task: ...

    async def create_input_required_task(
        self,
        server_id: str,
        method: str,
        parameters: JSONDict,
        message: str,
    ) -> JSONDict: ...
