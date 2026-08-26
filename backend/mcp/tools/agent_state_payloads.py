"""SoAI - MCP agent plan and todo state payload helpers [backend/mcp/tools/agent_state_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING

from core.agent.state_errors import AgentStateRevisionConflictError
from core.agent.state_payloads import (
    read_agent_plan_payload,
    read_agent_todo_payload,
)
from core.agent.state_persistence import (
    persist_agent_plan_write,
    persist_agent_todo_write,
)
from core.errors.exceptions import StateError, ValidationError
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "get_todo_payload",
    "persist_plan_payload",
    "persist_todo_payload",
    "read_plan_payload",
    "run_agent_state_write_operation",
)


async def run_agent_state_write_operation(
    operation_action: Awaitable[JSONDict],
    *,
    conflict_message: str,
) -> JSONDict:
    try:
        return await operation_action
    except AgentStateRevisionConflictError as exception:
        raise MCPToolError(-32603, conflict_message) from exception
    except (StateError, ValidationError) as exception:
        raise MCPToolError(-32602, str(exception)) from exception


async def read_plan_payload(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    conv_id: str,
    user_id: int,
) -> JSONDict:
    return await read_agent_plan_payload(
        database_agent_plan=utility_tools.database_agent_plan,
        conv_id=conv_id,
        user_id=user_id,
    )


async def persist_plan_payload(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    conv_id: str,
    user_id: int,
    title_value: JSONValue,
    markdown_value: JSONValue,
) -> JSONDict:
    persisted_write = await persist_agent_plan_write(
        database_agent_event_sequences=utility_tools.database_agent_event_sequences,
        database_agent_plan=utility_tools.database_agent_plan,
        conv_id=conv_id,
        user_id=user_id,
        title_value=title_value,
        markdown_value=markdown_value,
        require_no_running_root_turn=False,
    )
    return persisted_write.payload


async def get_todo_payload(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    conv_id: str,
    user_id: int,
) -> JSONDict:
    return await read_agent_todo_payload(
        database_agent_todo_state=utility_tools.database_agent_todo_state,
        conv_id=conv_id,
        user_id=user_id,
    )


async def persist_todo_payload(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    conv_id: str,
    user_id: int,
    todo_value: JSONValue,
    explanation_value: JSONValue,
) -> JSONDict:
    persisted_write = await persist_agent_todo_write(
        database_agent_event_sequences=utility_tools.database_agent_event_sequences,
        database_agent_todo_state=utility_tools.database_agent_todo_state,
        conv_id=conv_id,
        user_id=user_id,
        todo_value=todo_value,
        explanation_value=explanation_value,
        require_no_running_root_turn=False,
    )
    return persisted_write.payload
