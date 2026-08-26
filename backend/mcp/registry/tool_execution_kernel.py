"""SoAI - MCP registry registered tool execution kernel [backend/mcp/registry/tool_execution_kernel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric_lenient import coerce_lenient_bounded_float
from core.errors.exceptions import ValidationError
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.tool_handler_execution import (
    invoke_tool_handler_with_timeout,
    resolve_tool_timeout_sec,
)
from mcp.registry.workspace_initialization import (
    initialize_runtime_workspace_from_manager,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.registry.internal_protocols import MCPRegistryManagerProtocol

__all__ = (
    "RegisteredToolExecutionResult",
    "execute_registered_tool",
    "initialize_registered_tool_workspace",
)

_GENERATE_IMAGE_TOOL_NAME = "generate_image"


@dataclass(frozen=True, slots=True)
class RegisteredToolExecutionResult:
    result_payload: JSONValue
    timeout_sec: float


async def execute_registered_tool(
    manager: MCPRegistryManagerProtocol,
    *,
    client_id: str,
    user_id: int,
    tool_name: str,
    arguments: JSONDict,
    logger: LoggerProtocol,
    workspace_initialized: bool = False,
) -> RegisteredToolExecutionResult:
    handler = manager.state.registration.registered_tools[tool_name]
    if not workspace_initialized:
        await initialize_registered_tool_workspace(
            manager,
            client_id=client_id,
            user_id=user_id,
            tool_name=tool_name,
            arguments=arguments,
        )
    timeout_sec = _resolve_registered_tool_timeout_sec(manager, tool_name)
    result_payload = await invoke_tool_handler_with_timeout(
        handler=handler,
        arguments=arguments,
        tool_name=tool_name,
        timeout_sec=timeout_sec,
        logger=logger,
    )
    return RegisteredToolExecutionResult(
        result_payload=result_payload,
        timeout_sec=timeout_sec,
    )


async def initialize_registered_tool_workspace(
    manager: MCPRegistryManagerProtocol,
    *,
    client_id: str,
    user_id: int,
    tool_name: str,
    arguments: JSONDict,
) -> None:
    try:
        await initialize_runtime_workspace_from_manager(
            manager,
            arguments=arguments,
            user_id=user_id,
            owner_key=client_id,
            tool_name=tool_name,
        )
    except ValidationError as exception:
        raise MCPJSONRPCError(-32602, str(exception)) from exception


def _resolve_registered_tool_timeout_sec(
    manager: MCPRegistryManagerProtocol,
    tool_name: str,
) -> float:
    configured_timeout_sec = resolve_tool_timeout_sec(manager.tasks_tool_timeout_sec)
    if tool_name != _GENERATE_IMAGE_TOOL_NAME:
        return configured_timeout_sec
    image_timeout_sec = _resolve_generate_image_timeout_sec(manager)
    return max(configured_timeout_sec, image_timeout_sec + INTERACTIVE_TIMEOUT_SEC)


def _resolve_generate_image_timeout_sec(manager: MCPRegistryManagerProtocol) -> float:
    engine_value = manager.config.get("TOOLS.MCP.GENERATE_IMAGE.ENGINE")
    engine = engine_value.strip().lower() if isinstance(engine_value, str) else "automatic1111"
    if engine == "ai_horde":
        return coerce_lenient_bounded_float(
            manager.config.get("TOOLS.MCP.GENERATE_IMAGE.AI_HORDE.MAX_GENERATION_WAIT_SEC"),
            default=3600.0,
            minimum=60.0,
            maximum=21600.0,
        )
    return coerce_lenient_bounded_float(
        manager.config.get("TOOLS.MCP.GENERATE_IMAGE.TIMEOUT_SEC"),
        default=3600.0,
        minimum=1.0,
        maximum=21600.0,
    )
