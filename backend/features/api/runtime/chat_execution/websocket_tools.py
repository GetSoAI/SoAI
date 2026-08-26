"""SoAI - WebSocket chat MCP tool preparation [backend/features/api/runtime/chat_execution/websocket_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from features.api.runtime.tool_request.preparation import prepare_mcp_tools_for_request

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.request_message_source import (
        AgenticRequestMessageSource,
    )
    from features.api.runtime.context import ApiContext
    from features.api.runtime.tool_request.preparation import PreparedMCPToolRequest

__all__ = ("prepare_websocket_chat_tools",)

OPERATION_PREPARE_TOOLS = "webui_ws_chat_stream.start.prepare_tools"


async def prepare_websocket_chat_tools(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    request_context: RequestContext,
    request_json: JSONDict,
    trace_id: str | None,
    logger: LoggerProtocol,
    message_index: int,
    assistant_at_ms: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    extra_system_messages: tuple[str, ...],
    request_id: str,
    agentic_message_source: AgenticRequestMessageSource | None = None,
) -> tuple[PreparedMCPToolRequest | None, str | None, str | None]:
    try:
        prepared_tool_context = await prepare_mcp_tools_for_request(
            request=request,
            api_context=api_context,
            request_json=request_json,
            context=request_context,
            request_source=REQUEST_SOURCE_WEBUI_WS,
            message_index=message_index,
            assistant_at_ms=assistant_at_ms,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            extra_system_messages=extra_system_messages,
            knowledge_prompt_mode="real_send",
            knowledge_prompt_request_id=request_id,
            agentic_message_source=agentic_message_source,
        )
        request_context.mcp_tool_context = prepared_tool_context.tool_context
        return (prepared_tool_context, None, None)
    except SoAIError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to prepare MCP tools for WebSocket chat stream (invalid request).",
            trace_id=trace_id,
            operation=OPERATION_PREPARE_TOOLS,
            level="debug",
        )
        return (None, str(exception.code), str(exception))
    except (AttributeError, KeyError, TypeError, ValueError) as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_PREPARE_TOOLS)
        log_exception(
            logger,
            coerced,
            message="Failed to prepare MCP tools for WebSocket chat stream.",
            trace_id=trace_id,
            operation=OPERATION_PREPARE_TOOLS,
            level="warning",
        )
        return (None, str(coerced.code), str(coerced))
