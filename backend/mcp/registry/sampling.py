"""SoAI - MCP host sampling handlers [backend/mcp/registry/sampling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.protocols_main import MCPServerProtocol
from core.mcp.protocols_runtime import MCPRemoteHostProtocol
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.types.json_value import coerce_json_dict
from core.validation.booleans import parse_bool
from mcp.host.internal_protocols import MCPServerHostProtocol
from mcp.host.sampling import (
    openai_response_to_sampling_result,
    sampling_params_to_openai_payload,
)
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.inference import run_inference_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_host_sampling_create_message",
    "resolve_sampling_task",
)

LOGGER_NAME = "SoAI.mcp.registry.sampling"
OPERATION_MCP_REGISTRY_SAMPLING_COERCE_TOOLS_PROVIDED = (
    "mcp.registry.sampling.coerce_tools_provided"
)
OPERATION_MCP_REGISTRY_SAMPLING_RESOLVE_SAMPLING_TASK = (
    "mcp.registry.sampling.resolve_sampling_task"
)


def _coerce_tools_provided(parameters: JSONDict) -> bool:
    tools_value = parameters.get("tools")
    if isinstance(tools_value, list):
        return bool(tools_value)
    try:
        parsed = parse_bool(tools_value, default=False)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to parse tools flag (non-critical).",
            operation=OPERATION_MCP_REGISTRY_SAMPLING_COERCE_TOOLS_PROVIDED,
            level="debug",
        )
        return False
    if parsed is None:
        return False
    return bool(parsed)


async def resolve_sampling_task(manager: MCPServerProtocol, task: Task, action: str) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    if action not in ("approve", "decline", "cancel"):
        raise MCPJSONRPCError(-32602, f"Invalid sampling action: {action}")
    metadata = task.metadata
    parameters = coerce_json_dict(metadata.get("params")) or {}
    if action == "cancel":
        await manager.task.cancel_task(task.task_id, "User cancelled sampling request")
    elif action == "decline":
        await manager.task.fail_task(task.task_id, -32603, "User rejected sampling request")
    else:
        await manager.task.update_task_non_terminal_status(
            task.task_id,
            TaskStatus.WORKING,
            "Processing sampling request",
        )
        if not manager.model_information_service:
            await manager.task.fail_task(
                task.task_id,
                -32603,
                "Model information service not available",
            )
        else:
            try:
                payload = sampling_params_to_openai_payload(
                    parameters,
                    manager.host_sampling_default_model,
                )
                response_value = await run_inference_payload(
                    manager,
                    payload,
                    "mcp_sampling_create_message",
                )
                response = coerce_json_dict(response_value)
                if response is None:
                    raise MCPJSONRPCError(-32603, "Sampling inference response must be an object")
                sampling_result = openai_response_to_sampling_result(
                    response,
                    _coerce_tools_provided(parameters),
                )
                await manager.task.complete_task(task.task_id, sampling_result)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Sampling task failed.",
                    operation=OPERATION_MCP_REGISTRY_SAMPLING_RESOLVE_SAMPLING_TASK,
                    details={"task_id": task.task_id, "action": action},
                    level="warning",
                )
                await manager.task.fail_task(task.task_id, -32603, str(exception))
    updated_task = await manager.task.get_task(task.task_id)
    return manager.task.build_task_response(updated_task or task)


async def handle_host_sampling_create_message(
    remote: MCPRemoteHostProtocol,
    server: MCPServerHostProtocol,
    parameters: JSONDict,
    server_id: str,
) -> JSONDict:
    if not remote.host_sampling_enabled:
        raise MCPJSONRPCError(-32601, "Sampling feature is not enabled")
    if not server.tasks_enabled:
        raise MCPJSONRPCError(-32601, "Tasks feature is not enabled")
    if "task" not in parameters:
        raise MCPJSONRPCError(-32600, "Task augmentation is required for sampling/createMessage")
    sampling_params_to_openai_payload(parameters, server.host_sampling_default_model)
    return await server.task.create_input_required_task(
        server_id,
        "sampling/createMessage",
        parameters,
        "Awaiting user approval for sampling request",
    )
