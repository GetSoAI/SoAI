"""SoAI - MCP host elicitation handlers [backend/mcp/registry/elicitation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.protocols_runtime import MCPRemoteHostProtocol
from core.tasks.task import Task
from core.types.json_value import coerce_json_dict
from mcp.host.elicitation import (
    get_elicitation_mode,
    validate_elicitation_content,
    validate_elicitation_request_params,
    validate_elicitation_schema,
)
from mcp.host.internal_protocols import MCPServerHostProtocol
from mcp.protocol.types import MCPJSONRPCError
from mcp.server.handlers.task_payloads import build_task_response

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "clear_pending_url_elicitation",
    "handle_host_elicitation_create",
    "resolve_elicitation_task",
)


async def clear_pending_url_elicitation(
    remote: MCPRemoteHostProtocol,
    task: Task,
) -> None:
    parameters = coerce_json_dict(task.metadata.get("params")) or {}
    if get_elicitation_mode(parameters) != "url":
        return
    elicitation_id = parameters.get("elicitationId")
    if isinstance(elicitation_id, str) and elicitation_id:
        await remote.clear_pending_url_elicitation_for_task(
            task.owner_id,
            elicitation_id,
            task.task_id,
        )


async def resolve_elicitation_task(
    server: MCPServerHostProtocol,
    remote: MCPRemoteHostProtocol,
    task: Task,
    action: str,
    content: JSONDict | None,
) -> JSONDict:
    if action not in ("accept", "decline", "cancel"):
        raise MCPJSONRPCError(-32602, f"Invalid elicitation action: {action}")
    if content is not None and (not isinstance(content, dict)):
        raise MCPJSONRPCError(-32602, "Invalid content for elicitation response")
    metadata = task.metadata
    parameters_value = metadata.get("params")
    parameters = coerce_json_dict(parameters_value) or {}
    mode = get_elicitation_mode(parameters)
    if action == "accept":
        if mode == "form":
            if content is None:
                raise MCPJSONRPCError(-32602, "Elicitation form accept requires content")
            schema = parameters.get("requestedSchema")
            schema_dict = coerce_json_dict(schema)
            if schema_dict is None:
                raise MCPJSONRPCError(-32602, "Missing requestedSchema for form elicitation")
            validate_elicitation_schema(schema_dict)
            validate_elicitation_content(content, schema_dict)
        elif content is not None:
            raise MCPJSONRPCError(-32602, "Elicitation url accept must not include content")
    elif content is not None:
        raise MCPJSONRPCError(-32602, "Elicitation decline/cancel must not include content")
    result: JSONDict = {"action": action}
    if action == "accept" and mode == "form" and content is not None:
        result["content"] = content
    if mode == "url" and action in ("decline", "cancel"):
        await clear_pending_url_elicitation(remote, task)
    await server.task.complete_task(task.task_id, result)
    updated_task = await server.task.get_task(task.task_id)
    return build_task_response(updated_task or task)


async def handle_host_elicitation_create(
    remote: MCPRemoteHostProtocol,
    server: MCPServerHostProtocol,
    parameters: JSONDict,
    server_id: str,
) -> JSONDict:
    if not remote.host_elicitation_enabled:
        raise MCPJSONRPCError(-32601, "Elicitation feature is not enabled")
    if not server.tasks_enabled:
        raise MCPJSONRPCError(-32601, "Tasks feature is not enabled")
    if "task" not in parameters:
        raise MCPJSONRPCError(-32600, "Task augmentation is required for elicitation/create")
    validate_elicitation_request_params(parameters)
    task_response = await server.task.create_input_required_task(
        server_id,
        "elicitation/create",
        parameters,
        "Awaiting user input for elicitation request",
    )
    if get_elicitation_mode(parameters) == "url":
        elicitation_id = parameters.get("elicitationId")
        if elicitation_id and isinstance(elicitation_id, str):
            task_entry = task_response.get("task")
            task_id_value = task_entry.get("taskId") if isinstance(task_entry, dict) else None
            if isinstance(task_id_value, str) and task_id_value:
                await remote.record_pending_url_elicitation(
                    server_id,
                    elicitation_id,
                    task_id_value,
                )
    return task_response
