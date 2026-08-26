"""SoAI - MCP host-interaction task listing and resolution [backend/mcp/server/handlers/task_interactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import (
    TASK_TYPE_MCP_ELICITATION,
    TASK_TYPE_MCP_SAMPLING,
)
from core.timing.epoch import epoch_ms
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.elicitation import clear_pending_url_elicitation, resolve_elicitation_task
from mcp.registry.sampling import resolve_sampling_task

if TYPE_CHECKING:
    from core.mcp.protocols_runtime import MCPRemoteHostProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from mcp.host.internal_protocols import MCPServerHostProtocol

__all__ = (
    "expire_host_interaction",
    "list_pending_host_interactions",
    "resolve_host_interaction",
)

_HOST_INTERACTION_METHODS: frozenset[str] = frozenset(
    {
        "elicitation/create",
        "sampling/createMessage",
    },
)
HOST_INTERACTION_TIMEOUT_MESSAGE = "Timed out waiting for user input."


async def expire_host_interaction(
    server_ref: MCPServerHostProtocol,
    remote: MCPRemoteHostProtocol,
    task: Task,
) -> Task | None:
    await server_ref.task.fail_task(
        task.task_id,
        504,
        HOST_INTERACTION_TIMEOUT_MESSAGE,
    )
    finalized = await server_ref.task.get_task(task.task_id)
    if finalized is not None and finalized.status == TaskStatus.FAILED:
        if task.task_type == TASK_TYPE_MCP_ELICITATION:
            await clear_pending_url_elicitation(remote, task)
    return finalized


async def list_pending_host_interactions(
    task_registry_queries: TaskRegistryQueryView,
) -> list[JSONDict]:
    tasks = await task_registry_queries.query_active(
        task_type=TASK_TYPE_MCP_SAMPLING,
    ) + await task_registry_queries.query_active(task_type=TASK_TYPE_MCP_ELICITATION)
    now_ms = epoch_ms()
    return [
        {
            "task_id": task_entry.task_id,
            "method": normalized_method,
            "client_id": task_entry.owner_id,
            "status": task_entry.status.value,
            "created_at_ms": int(task_entry.created_at_ms),
            "params": (
                params if isinstance((params := task_entry.metadata.get("params")), dict) else None
            ),
        }
        for task_entry in tasks
        if task_entry.status == TaskStatus.INPUT_REQUIRED
        and (task_entry.ttl_expires_at_ms is None or task_entry.ttl_expires_at_ms > now_ms)
        and isinstance((method_value := task_entry.metadata.get("method")), str)
        and (normalized_method := method_value.strip()) in _HOST_INTERACTION_METHODS
    ]


async def resolve_host_interaction(
    server_ref: MCPServerHostProtocol,
    remote: MCPRemoteHostProtocol,
    task: Task,
    action: str,
    content: JSONDict | None = None,
) -> JSONDict:
    method = task.metadata.get("method", "")
    if method == "elicitation/create":
        return await resolve_elicitation_task(
            server_ref,
            remote,
            task,
            action,
            content,
        )
    if method == "sampling/createMessage":
        return await resolve_sampling_task(server_ref, task, action)
    raise MCPJSONRPCError(-32602, f"Unsupported host interaction task: {method}")
