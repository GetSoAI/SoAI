"""SoAI - OpenAI MCP tool selection and persistence [backend/features/api/routes/openai/tool_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.runtime.context import ApiContext

__all__ = ("persist_conversation_tool_defaults",)

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
