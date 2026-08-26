"""SoAI - MCP/OpenAI tool execution helpers [backend/mcp/bridge/executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError
from core.errors.external_service_exception import MCPError
from core.errors.public_projection import project_public_exception
from core.logging.trace import get_logger
from core.mcp.protocols_main import MCPRemoteProtocol, MCPServerProtocol
from core.mcp.qualified_name import decode_qualified_tool_name
from core.mcp.tool_name_suggestions import (
    append_tool_suggestions_to_message,
    build_tool_name_candidates_from_names,
    build_tool_name_candidates_from_remote_tools,
    suggest_tool_names,
)
from core.tasks.enums import TaskStatus
from core.types.json_value import is_json_value
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.tool_result_envelopes import (
    build_proxied_task_completion_payload,
    build_proxied_task_error_payload,
)
from mcp.shared.exception_boundary import (
    resolve_mcp_boundary_rpc_code,
    resolve_mcp_boundary_rpc_data,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "await_proxied_task_completion",
    "execute_mcp_tool",
)

LOGGER_NAME = "SoAI.mcp.bridge.executor"
OPERATION_EXECUTE_MCP_TOOL = "mcp.bridge.execute_mcp_tool"


def _build_unknown_mcp_tool_error(
    *,
    tool_name: str,
    local_tool_names: Mapping[str, Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]],
    remote_tools: list[JSONDict],
) -> MCPJSONRPCError:
    suggestions = suggest_tool_names(
        tool_name,
        (
            *build_tool_name_candidates_from_names(local_tool_names.keys()),
            *build_tool_name_candidates_from_remote_tools(remote_tools),
        ),
    )
    return MCPJSONRPCError(
        -32602,
        append_tool_suggestions_to_message(f"Unknown MCP tool: {tool_name}", suggestions),
        data={
            "requested_tool_name": tool_name,
            "suggested_tool_names": list(suggestions),
        },
    )


def _build_jsonrpc_error_from_mcp_error(exception: MCPError) -> MCPJSONRPCError:
    return MCPJSONRPCError(
        exception.rpc_code,
        exception.message,
        exception.rpc_data,
    )


async def execute_mcp_tool(
    mcp_remote: MCPRemoteProtocol,
    handlers: Mapping[str, Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]],
    tool_name: str,
    arguments: JSONDict,
) -> JSONValue:
    try:
        if tool_name in handlers:
            handler_result = handlers[tool_name](arguments)
            if is_json_value(handler_result):
                return handler_result
            if inspect.isawaitable(handler_result):
                awaited_result = await handler_result
                if is_json_value(awaited_result):
                    return awaited_result
                raise MCPJSONRPCError(-32603, "MCP tool handlers must return a JSON result.")
            raise MCPJSONRPCError(-32603, "MCP tool handlers must return a JSON result.")
        server_id, name = decode_qualified_tool_name(tool_name)
        if server_id is not None:
            if not name:
                raise MCPJSONRPCError(-32602, "Invalid MCP tool name.")
            remote_tools = await mcp_remote.list_all_tools()
            if not any(
                isinstance(remote_tool.get("server_id"), str)
                and isinstance(remote_tool.get("name"), str)
                and remote_tool.get("server_id") == server_id
                and remote_tool.get("name") == name
                for remote_tool in remote_tools
            ):
                raise _build_unknown_mcp_tool_error(
                    tool_name=tool_name,
                    local_tool_names=handlers,
                    remote_tools=remote_tools,
                )
            return await mcp_remote.invoke_tool(server_id, name, arguments)
        remote_tools = await mcp_remote.list_all_tools()
        raise _build_unknown_mcp_tool_error(
            tool_name=tool_name,
            local_tool_names=handlers,
            remote_tools=remote_tools,
        )
    except asyncio.CancelledError:
        raise
    except MCPJSONRPCError:
        raise
    except MCPError as exception:
        raise _build_jsonrpc_error_from_mcp_error(exception) from exception
    except Exception as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_EXECUTE_MCP_TOOL,
        )
        log_exception(
            logger,
            coerced,
            message="MCP tool dispatch failed.",
            operation=OPERATION_EXECUTE_MCP_TOOL,
            details={"tool_name": tool_name},
        )
        raise MCPJSONRPCError(
            resolve_mcp_boundary_rpc_code(exception),
            coerced.message,
            resolve_mcp_boundary_rpc_data(exception),
        ) from exception


async def await_proxied_task_completion(
    mcp_server: MCPServerProtocol,
    task_id: str,
    *,
    tool_name: str,
) -> JSONDict:
    timeout_value = mcp_server.task_proxy_timeout_seconds
    timeout_sec: float | None = (
        float(timeout_value) if isinstance(timeout_value, int | float) else None
    )
    try:
        task = await mcp_server.task_registry.wait_for_completion(task_id, timeout=timeout_sec)
    except (SoAITimeoutError, TimeoutError) as exception:
        raise MCPJSONRPCError(
            -32603,
            project_public_exception(exception).message,
            data={"tool_name": tool_name, "task_id": task_id},
        ) from exception
    if task is None:
        raise MCPJSONRPCError(
            -32603,
            f"Background task not found: {task_id}",
            data={"tool_name": tool_name, "task_id": task_id},
        )
    if task.status is TaskStatus.COMPLETED:
        return build_proxied_task_completion_payload(
            task_id=task_id,
            status=task.status,
            result=task.result,
            error_message=task.error_message,
        )
    error_message = task.error_message or "Background task did not complete successfully."
    error_payload = build_proxied_task_error_payload(
        task_id=task_id,
        status=task.status,
        result=task.result,
        error_message=error_message,
    )
    raise MCPJSONRPCError(
        -32603,
        error_message,
        data={"tool_name": tool_name, "task_id": task_id, "result": error_payload},
    )
