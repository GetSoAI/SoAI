"""SoAI - Structured subagent parent tool call update publishing [backend/features/agent/subagents/parent_tool_call_update_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallDependencies
from core.tool_calls.live_update_identity import ToolCallLiveUpdateIdentity
from core.tool_calls.live_update_publishing import publish_tool_call_live_update

if TYPE_CHECKING:
    from core.tool_calls.deferred_tool_call_row import DeferredToolCallRow
    from core.types.json import JSONDict

__all__ = ("publish_parent_tool_call_updated_event_noncritical",)

OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_PUBLISH = (
    "agent.subagents.parent_tool_call_updates.publish"
)


async def publish_parent_tool_call_updated_event_noncritical(
    *,
    deps: DeferredToolCallDependencies,
    row: DeferredToolCallRow,
    result_payload: JSONDict,
) -> None:
    try:
        await publish_tool_call_live_update(
            event_bus=deps.event_bus,
            database_tool_calls=deps.database_tool_calls,
            identity=ToolCallLiveUpdateIdentity(
                user_id=int(deps.user_id),
                conv_id=row.conv_id,
                request_id=None,
                assistant_at_ms=row.assistant_at_ms,
                assistant_turn_at_ms=row.assistant_turn_at_ms,
                model_variant_index=row.model_variant_index,
            ),
            call_id=deps.call_id,
            event_type="tool_call_updated",
            tool_payload={
                "call_id": deps.call_id,
                "tool_name": deps.tool_name,
                "status": "running",
                "message_index": row.message_index,
                "assistant_turn_at_ms": row.assistant_turn_at_ms,
                "model_variant_index": row.model_variant_index,
                "sequence_index": row.sequence_index,
                "content_index_before": row.content_index_before,
                "thinking_index_before": row.thinking_index_before,
                "thinking_duration_before_ms": row.thinking_duration_before_ms,
                "arguments": row.tool_arguments_json,
                "result": result_payload,
                "collapsed": True,
            },
            status="running",
            duration_ms=None,
            started_at_ms=None,
            tool_result=result_payload,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_PUBLISH,
            trace_id=deps.trace_id,
        )
        log_handled_exception(
            deps.logger,
            coerced,
            message="Failed to publish structured parent tool call update for subagent (non-critical).",
            trace_id=deps.trace_id,
            operation=OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_PUBLISH,
            level="warning",
            details={"call_id": deps.call_id},
        )
