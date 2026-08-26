"""SoAI - OpenAI MCP tool selection and persistence [backend/features/api/routes/openai/tool_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent_mode import is_plan_or_execute_agent_mode
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.default_tool_names import (
    DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS,
    DEFAULT_CONVERSATION_MCP_PLAN_TOOLS,
    DEFAULT_CONVERSATION_MCP_TOOLS,
)
from core.runtime.protocols import RequestProtocol
from core.types.json import JSONDict
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import (
    raise_invalid_request,
)

__all__ = (
    "persist_conversation_tool_defaults",
    "reconcile_selected_names",
)

LOGGER_NAME = "SoAI.features.api.tool_selection"
OPERATION = "api_openai.prepare_tools.persist_conversation_tool_defaults"


async def persist_conversation_tool_defaults(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    tool_field: str,
    expected_tools_enabled: bool,
    expected_tools: list[str],
    tools_enabled: bool,
    updated_tools: list[str],
    trace_id: str | None,
) -> None:
    try:
        async with api_context.dependencies.conversation_agent_settings_locks.lock(
            (user_id, conv_id),
        ):
            await api_context.dependencies.database_conversations.reconcile_conversation_tool_defaults(
                conv_id=conv_id,
                user_id=user_id,
                tool_field=tool_field,
                expected_tools_enabled=expected_tools_enabled,
                expected_tools=expected_tools,
                tools_enabled=tools_enabled,
                updated_tools=updated_tools,
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="api_openai.prepare_tools.persist_conversation_tool_defaults",
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to persist updated conversation tool defaults.",
            trace_id=trace_id,
            operation=OPERATION,
            level="warning",
        )


async def reconcile_selected_names(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    selected_names: list[str],
    allowed_tool_map: dict[str, JSONDict],
    tools_provided: bool,
    tools_enabled: bool,
    agent_mode: str,
    choice_mode: str | None,
    choice_name: str | None,
    resolved_conv_id: str,
    user_id: int,
    trace_id: str | None,
) -> tuple[list[str], str | None, str | None]:
    if (not tools_provided) and selected_names:
        missing_defaults = [name for name in selected_names if name not in allowed_tool_map]
        if missing_defaults:
            if agent_mode == "plan":
                tool_field = "plan_tools"
                canonical_defaults = DEFAULT_CONVERSATION_MCP_PLAN_TOOLS
            elif agent_mode == "execute":
                tool_field = "execute_tools"
                canonical_defaults = DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS
            else:
                tool_field = "default_tools"
                canonical_defaults = DEFAULT_CONVERSATION_MCP_TOOLS
            sanitized_names = [name for name in selected_names if name in allowed_tool_map]
            if not sanitized_names:
                sanitized_names = [name for name in canonical_defaults if name in allowed_tool_map]
            if is_plan_or_execute_agent_mode(agent_mode) and not sanitized_names:
                raise_invalid_request(
                    request,
                    "The conversation tool configuration contains no available tools for the active mode.",
                )
            updated_tools_enabled = tools_enabled and bool(sanitized_names)
            if sanitized_names != selected_names or updated_tools_enabled != tools_enabled:
                await persist_conversation_tool_defaults(
                    api_context=api_context,
                    conv_id=resolved_conv_id,
                    user_id=user_id,
                    tool_field=tool_field,
                    expected_tools_enabled=tools_enabled,
                    expected_tools=list(selected_names),
                    tools_enabled=updated_tools_enabled,
                    updated_tools=sanitized_names,
                    trace_id=trace_id,
                )
                tools_enabled = updated_tools_enabled
                selected_names = list(sanitized_names)
    return (selected_names, choice_mode, choice_name)
