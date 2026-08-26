"""SoAI - MCP server internal protocols [backend/mcp/server/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol, override

from core.mcp.protocols_main import MCPServerProtocol
from mcp.registry.internal_protocols import (
    MCPRegistryManagerProtocol,
    MCPTaskHandlerManagerProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.mcp.protocols_main import MCPRemoteProtocol, MCPSearchProtocol
    from core.metrics.protocols import MetricsRecorderProtocol
    from core.tasks.enums import TaskStatus
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue
    from mcp.host.internal_protocols import MCPServerHostProtocol
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol
    from mcp.server.handlers.lifecycle_manager import MCPLifecycleManager
    from mcp.server.handlers.notification_service import MCPNotificationService
    from mcp.tools.service import MCPUtilityTools

    type PromptHandler = Callable[[JSONDict], Awaitable[JSONDict]]
    type CoreToolHandler = Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]

__all__ = (
    "BackgroundTaskTrackerProtocol",
    "MCPBackgroundTaskSurface",
    "MCPRegistrationStateSurface",
    "MCPServerDispatchSurface",
    "MCPServerRuntimeLifecycleSurface",
    "MCPServerRuntimePropertiesSurface",
    "MCPServerStateSurface",
    "MCPTaskStatusUpdateSurface",
    "OpenAIExecutionServerProtocol",
    "OpenAIExecutionStateProtocol",
)


class BackgroundTaskTrackerProtocol(Protocol):
    def track(self, task: asyncio.Task[None]) -> asyncio.Task[None]: ...


class MCPBackgroundTaskSurface(Protocol):
    @property
    def background_tasks(self) -> BackgroundTaskTrackerProtocol: ...


class MCPServerDispatchSurface(MCPRegistryManagerProtocol, MCPTaskHandlerManagerProtocol, Protocol):
    @property
    def server_mode_active(self) -> bool: ...


class MCPTaskStatusUpdateSurface(Protocol):
    @property
    def metrics_manager(self) -> MetricsRecorderProtocol: ...

    def resolve_session_id(self, client_id: str) -> str: ...

    async def has_client_session(self, session_id: str) -> bool: ...

    async def ensure_client_session(
        self,
        session_id: str,
        protocol_version: str,
        sequence: int,
    ) -> None: ...

    async def emit_client_stream_message(self, session_id: str, message: JSONDict) -> None: ...

    def require_task_registry(self) -> TaskRegistryProtocol: ...

    def require_task_registry_queries(self) -> TaskRegistryQueryView: ...

    async def get_task(self, task_id: str) -> Task | None: ...

    @property
    def server_ref(self) -> MCPServerHostProtocol: ...

    async def send_task_status_notification(self, task: Task) -> None: ...

    async def update_task_to_terminal_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        result: JSONDict | None = None,
        error_code: int | None = None,
        error_message: str | None = None,
        status_message: str | None = None,
    ) -> None: ...

    async def update_task_non_terminal_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str,
    ) -> None: ...

    async def create_task(self, client_id: str, method: str, parameters: JSONDict) -> Task: ...


class MCPServerRuntimeLifecycleSurface(Protocol):
    lifecycle_manager: MCPLifecycleManager | None

    @property
    def notification(self) -> MCPNotificationService: ...

    def track_background_task(self, task: asyncio.Task[None]) -> None: ...


class MCPRegistrationStateSurface(Protocol):
    @property
    def registered_prompts(self) -> dict[str, PromptHandler]: ...


class MCPServerStateSurface(Protocol):
    @property
    def registration(self) -> MCPRegistrationStateSurface: ...


class MCPServerRuntimePropertiesSurface(Protocol):
    @property
    def state(self) -> MCPServerStateSurface: ...


class OpenAIExecutionStateProtocol(Protocol):
    @property
    def mcp_rag(self) -> MCPRAGInternalProtocol | None: ...

    @property
    def mcp_search(self) -> MCPSearchProtocol | None: ...


class OpenAIExecutionServerProtocol(MCPServerProtocol, Protocol):
    @property
    def mcp_remote(self) -> MCPRemoteProtocol: ...

    @property
    @override
    def utility_tools(self) -> MCPUtilityTools: ...

    @property
    def core_tool_handlers(self) -> dict[str, CoreToolHandler]: ...

    @property
    def state(self) -> OpenAIExecutionStateProtocol: ...
