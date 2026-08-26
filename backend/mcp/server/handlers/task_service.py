"""SoAI - MCP server task lifecycle management and notification service [backend/mcp/server/handlers/task_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_TASKS_CREATED,
)
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeId
from mcp.host.internal_protocols import MCPServerHostProtocol
from mcp.protocol.types import MCPJSONRPCError
from mcp.server.handlers.task_payloads import (
    build_task_entry,
    build_task_response,
    extract_task_id_parameter,
)
from mcp.server.handlers.task_service_host_interactions import (
    list_pending_host_interactions_method,
    resolve_host_interaction_method,
)
from mcp.server.handlers.task_service_status_updates import (
    cancel_task_method,
    complete_task_method,
    create_input_required_task_method,
    fail_task_method,
    send_task_status_notification_method,
    update_task_non_terminal_status_method,
    update_task_to_terminal_status_method,
)
from mcp.server.handlers.task_types import method_to_task_type

if TYPE_CHECKING:
    from core.mcp.protocols_runtime import MCPRemoteHostProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.types.json import JSONDict
    from mcp.protocol.types import MCPClientSession
    from mcp.server.state import MCPServerState

__all__ = (
    "MCPTaskService",
    "MCPTaskServiceDependencies",
)

LOGGER_NAME = "SoAI.mcp.server.task_service"


@dataclass(frozen=True, slots=True)
class MCPTaskServiceDependencies:
    state: MCPServerState
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    tasks_default_ttl_ms: int
    user_interaction_timeout_ms: int
    get_session: Callable[[str], MCPClientSession | None]
    resolve_session_id: Callable[[str], str]
    has_client_session: Callable[[str], Awaitable[bool]]
    ensure_client_session: Callable[[str, str | None, int], Awaitable[str]]
    emit_client_stream_message: Callable[[str, JSONDict], Awaitable[None]]
    metrics_manager: MetricsManagerProtocol
    server_ref: MCPServerHostProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPTaskServiceDependencies",
            emit_client_stream_message=self.emit_client_stream_message,
            ensure_client_session=self.ensure_client_session,
            get_session=self.get_session,
            has_client_session=self.has_client_session,
            metrics_manager=self.metrics_manager,
            resolve_session_id=self.resolve_session_id,
            server_ref=self.server_ref,
            state=self.state,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
            tasks_default_ttl_ms=self.tasks_default_ttl_ms,
            user_interaction_timeout_ms=self.user_interaction_timeout_ms,
        )


class MCPTaskService:
    def __init__(self, deps: MCPTaskServiceDependencies) -> None:
        self._state = deps.state
        self._task_registry = deps.task_registry
        self._task_registry_queries = deps.task_registry_queries
        self._tasks_default_ttl_ms = deps.tasks_default_ttl_ms
        self._user_interaction_timeout_ms = deps.user_interaction_timeout_ms
        self._get_session = deps.get_session
        self._resolve_session_id = deps.resolve_session_id
        self._has_client_session = deps.has_client_session
        self._ensure_client_session = deps.ensure_client_session
        self._emit_client_stream_message = deps.emit_client_stream_message
        self._metrics_manager = deps.metrics_manager
        self._server_ref = deps.server_ref

    async def send_task_status_notification(self, task: Task) -> None:
        await send_task_status_notification_method(self, task)

    async def update_task_to_terminal_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        result: JSONDict | None = None,
        error_code: int | None = None,
        error_message: str | None = None,
        status_message: str | None = None,
    ) -> None:
        await update_task_to_terminal_status_method(
            self,
            task_id,
            new_status,
            result=result,
            error_code=error_code,
            error_message=error_message,
            status_message=status_message,
        )

    async def complete_task(
        self,
        task_id: str,
        result: JSONDict,
        message: str | None = None,
    ) -> None:
        await complete_task_method(self, task_id, result, message)

    async def fail_task(self, task_id: str, code: int, message: str) -> None:
        await fail_task_method(self, task_id, code, message)

    async def cancel_task(self, task_id: str, reason: str = "Cancelled") -> None:
        await cancel_task_method(self, task_id, reason)

    async def update_task_non_terminal_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str,
    ) -> None:
        await update_task_non_terminal_status_method(self, task_id, status, message)

    async def create_input_required_task(
        self,
        server_id: str,
        method: str,
        parameters: JSONDict,
        message: str,
    ) -> JSONDict:
        return await create_input_required_task_method(
            self,
            server_id,
            method,
            parameters,
            message,
        )

    async def list_pending_host_interactions(self) -> list[JSONDict]:
        return await list_pending_host_interactions_method(self)

    async def resolve_host_interaction(
        self,
        remote: MCPRemoteHostProtocol,
        task_id: str,
        action: str,
        content: JSONDict | None = None,
    ) -> JSONDict:
        return await resolve_host_interaction_method(
            self,
            remote,
            task_id,
            action,
            content,
        )

    def resolve_session_id(self, client_id: str) -> str:
        return self._resolve_session_id(client_id)

    async def has_client_session(self, session_id: str) -> bool:
        return await self._has_client_session(session_id)

    async def ensure_client_session(
        self,
        session_id: str,
        protocol_version: str,
        sequence: int,
    ) -> None:
        await self._ensure_client_session(session_id, protocol_version, sequence)

    async def emit_client_stream_message(self, session_id: str, message: JSONDict) -> None:
        await self._emit_client_stream_message(session_id, message)

    @property
    def metrics_manager(self) -> MetricsManagerProtocol:
        return self._metrics_manager

    @property
    def server_ref(self) -> MCPServerHostProtocol:
        return self._server_ref

    async def get_task(self, task_id: str) -> Task | None:
        return await self._task_registry.get(task_id) if self._task_registry is not None else None

    def extract_task_id_parameter(self, parameters: JSONDict) -> str | None:
        return extract_task_id_parameter(parameters)

    def build_task_response(self, task: Task) -> JSONDict:
        return build_task_response(task)

    def build_task_entry(self, task: Task) -> JSONDict:
        return build_task_entry(task)

    def require_task_registry(self) -> TaskRegistryProtocol:
        if self._task_registry is None:
            raise MCPJSONRPCError(-32603, "Task registry not available")
        return self._task_registry

    def require_task_registry_queries(self) -> TaskRegistryQueryView:
        if self._task_registry_queries is None:
            raise MCPJSONRPCError(-32603, "Task registry queries not available")
        return self._task_registry_queries

    def method_to_task_type(self, method: str) -> TaskTypeId:
        return method_to_task_type(method)

    async def require_task_for_client(self, task_id: str, client_id: str) -> Task:
        task_registry = self.require_task_registry()
        task = await self.get_task(task_id)
        if not task or task.owner_id != client_id:
            raise MCPJSONRPCError(-32602, f"Task not found: {task_id}")
        if task.is_expired():
            await task_registry.delete(task_id)
            raise MCPJSONRPCError(-32602, f"Task expired: {task_id}")
        return task

    async def create_task(self, client_id: str, method: str, parameters: JSONDict | None) -> Task:
        logger = get_logger(LOGGER_NAME)
        task_registry = self.require_task_registry()
        task_type = method_to_task_type(method)
        session = self._get_session(self._resolve_session_id(client_id))
        cancellation_id = f"mcp_task:{client_id}:{method}:{uuid.uuid4().hex[:12]}"
        try:
            task = await create(
                task_registry,
                task_type=task_type,
                user_id=session.user_id if session else 0,
                owner_id=client_id,
                owner_type="mcp_client",
                cancellation_id=cancellation_id,
                status=TaskStatus.WORKING,
                ttl_ms=(
                    self._user_interaction_timeout_ms
                    if method in {"elicitation/create", "sampling/createMessage"}
                    else self._tasks_default_ttl_ms
                ),
                poll_interval_ms=1000,
                progress_total=100,
                metadata={"method": method, "params": parameters or {}},
            )
        except ValueError as exception:
            raise MCPJSONRPCError(-32603, str(exception)) from exception
        logger.debug("Created task %s for client %s: %s", task.task_id, client_id, method)
        self._metrics_manager.increment_counter(*MCP_SERVER_COUNTER_TASKS_CREATED)
        return task
