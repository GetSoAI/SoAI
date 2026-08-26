"""SoAI - MCP tool request context preparation [backend/features/api/runtime/tool_request/mcp_tool_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.tool_choice import ToolChoiceError
from core.mcp.tool_context_preparation import prepare_mcp_tool_context
from core.openai.request_fields import resolve_optional_model_name
from core.orchestrator.types import MCPToolContext
from core.runtime.request_trace_id import get_request_trace_id
from core.timing.epoch import epoch_ms
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.model_tool_calling import (
    build_supports_tool_calling_callable,
)
from features.api.runtime.conversation_message_counts import (
    resolve_conversation_message_count,
)
from features.api.runtime.errors import raise_invalid_request, raise_service_unavailable

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.context import ApiContext
    from features.api.runtime.tool_request.conversation_context import (
        ToolRequestConversationContext,
    )

__all__ = ("build_mcp_tool_context",)

LOGGER_NAME = "SoAI.features.api.mcp_tool_context"
OPERATION_COLLECT_MCP_TOOLS = "api_openai.collect_mcp_tools"


def _coerce_blocked_tools_details(details: Mapping[str, JSONValue] | None) -> JSONDict:
    if not isinstance(details, Mapping):
        return {}
    blocked_value = details.get("blocked_tools")
    if not isinstance(blocked_value, Mapping):
        return {}
    normalized: JSONDict = {}
    for tool_name, reason in blocked_value.items():
        if not isinstance(tool_name, str) or not tool_name.strip():
            continue
        if not isinstance(reason, str) or not reason.strip():
            continue
        normalized[tool_name.strip()] = reason.strip()
    return normalized


def _resolve_message_index(value: int | None, *, fallback: int) -> int:
    resolved = coerce_optional_non_negative_int_strict(value)
    return resolved if resolved is not None else int(fallback)


def _resolve_assistant_at_ms(value: int | None) -> int:
    resolved = coerce_optional_non_negative_int_strict(value)
    return resolved if resolved is not None else int(epoch_ms())


async def build_mcp_tool_context(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    request_json: JSONDict,
    conversation: ToolRequestConversationContext,
    message_index: int | None,
    assistant_at_ms: int | None,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    force_tool_approval_required: bool | None,
    forced_tool_names: tuple[str, ...] = (),
    force_tool_choice_auto: bool = False,
) -> MCPToolContext:
    trace_id = get_request_trace_id(request)
    message_count = await resolve_conversation_message_count(
        request=request,
        api_context=api_context,
        conv_id=conversation.resolved_conv_id,
        user_id=conversation.user_id,
    )
    resolved_message_index = _resolve_message_index(message_index, fallback=message_count)
    resolved_assistant_at_ms = _resolve_assistant_at_ms(assistant_at_ms)
    supports_tool_calling = build_supports_tool_calling_callable(api_context.dependencies)

    try:
        request_model_id = resolve_optional_model_name(request_json)
        context_model_id = coerce_optional_trimmed_str(conversation.requested_model)
        return await prepare_mcp_tool_context(
            request_json=request_json,
            agent_mode=conversation.agent_mode,
            normalized_mcp=conversation.normalized_mcp,
            conv_id=conversation.resolved_conv_id,
            user_id=int(conversation.user_id),
            message_index=resolved_message_index,
            assistant_at_ms=resolved_assistant_at_ms,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            model_id=context_model_id or request_model_id or "",
            is_automation=conversation.is_automation,
            config=api_context.dependencies.config,
            force_tool_approval_required=force_tool_approval_required,
            forced_tool_names=forced_tool_names,
            force_tool_choice_auto=force_tool_choice_auto,
            supports_tool_calling=supports_tool_calling,
            sources=api_context.dependencies,
            local_tool_catalog_scope=conversation.local_tool_catalog_scope,
        )
    except ToolChoiceError as exception:
        if exception.is_invalid_request:
            raise_invalid_request(
                request,
                exception.message,
                extra={"blocked_tools": _coerce_blocked_tools_details(exception.details)},
            )
        raise ValidationError(exception.message) from exception
    except ValidationError as exception:
        raise_invalid_request(
            request,
            str(exception),
            extra={"blocked_tools": _coerce_blocked_tools_details(exception.details)},
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_COLLECT_MCP_TOOLS,
            trace_id=trace_id,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to build MCP tool context.",
            trace_id=trace_id,
            operation=OPERATION_COLLECT_MCP_TOOLS,
            level="error",
        )
        raise_service_unavailable(request, "MCP tools are not available.")
    raise ValidationError("MCP tool context preparation failed.")
