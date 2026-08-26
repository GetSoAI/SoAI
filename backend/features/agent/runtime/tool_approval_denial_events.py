"""SoAI - Agent tool approval denial lifecycle events [backend/features/agent/runtime/tool_approval_denial_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.events.types_system import ToolCallCompletedEvent, ToolCallCreatedEvent
from core.tool_calls.chronology import (
    resolve_content_index_before,
    resolve_optional_thinking_duration_before_ms,
    resolve_sequence_index,
    resolve_thinking_index_before,
)
from core.tool_calls.error_payloads import (
    TOOL_CALL_USER_DENIED_ERROR_CODE,
    TOOL_CALL_USER_DENIED_ERROR_MESSAGE,
    build_tool_call_error_payload,
)
from core.tool_calls.status_values import TOOL_CALL_STATUS_ERROR

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict

__all__ = (
    "build_user_denied_tool_call_result_payload",
    "publish_user_denied_tool_call_events",
)


def build_user_denied_tool_call_result_payload() -> JSONDict:
    return build_tool_call_error_payload(
        error_message=TOOL_CALL_USER_DENIED_ERROR_MESSAGE,
        code=TOOL_CALL_USER_DENIED_ERROR_CODE,
    )


async def publish_user_denied_tool_call_events(
    *,
    request_context: RequestContext,
    tool_call: JSONDict,
    tool_call_id: str,
    tool_name: str,
    tool_arguments: str | None,
    user_id: int,
    conv_id: str,
    message_index: int,
    result_payload: JSONDict,
    publish_event: Callable[[Event], Awaitable[None]],
) -> None:
    sequence_index = resolve_sequence_index(tool_call)
    content_index_before = resolve_content_index_before(tool_call)
    thinking_index_before = resolve_thinking_index_before(tool_call)
    thinking_duration_before_ms = resolve_optional_thinking_duration_before_ms(tool_call)
    created_event = ToolCallCreatedEvent(
        user_id=user_id,
        conv_id=conv_id,
        call_id=tool_call_id,
        tool_name=tool_name,
        message_index=message_index,
        sequence_index=sequence_index,
        content_index_before=content_index_before,
        thinking_index_before=thinking_index_before,
        thinking_duration_before_ms=thinking_duration_before_ms,
        tool_arguments=tool_arguments,
        turn_id=request_context.agent_turn_id,
        iteration_index=request_context.agent_iteration_index,
    )
    await publish_event(created_event)
    completed_event = ToolCallCompletedEvent(
        user_id=user_id,
        conv_id=conv_id,
        call_id=tool_call_id,
        tool_name=tool_name,
        status=TOOL_CALL_STATUS_ERROR,
        message_index=message_index,
        sequence_index=sequence_index,
        content_index_before=content_index_before,
        thinking_index_before=thinking_index_before,
        thinking_duration_before_ms=thinking_duration_before_ms,
        tool_arguments=tool_arguments,
        result=result_payload,
        duration_ms=0,
        error_message=TOOL_CALL_USER_DENIED_ERROR_MESSAGE,
        code_diffs=None,
        turn_id=request_context.agent_turn_id,
        iteration_index=request_context.agent_iteration_index,
    )
    await publish_event(completed_event)
