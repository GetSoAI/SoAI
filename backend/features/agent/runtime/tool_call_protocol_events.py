"""SoAI - Tool-call protocol rejection events [backend/features/agent/runtime/tool_call_protocol_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_conversation import ToolCallCompletedEvent, ToolCallCreatedEvent
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.tool_calls.canonical_requests import build_canonical_tool_call_request
from core.tool_calls.chronology import resolve_required_non_negative_integer
from core.tool_calls.status_values import TOOL_CALL_STATUS_ERROR
from core.tool_calls.visibility import should_persist_visible_tool_call_rows
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.agent.turn_state_writer import TurnStateWriter
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue
    from features.agent.runtime.turn_engine import TurnPrimitives

__all__ = ("publish_rejected_tool_call_events",)


async def publish_rejected_tool_call_events(
    *,
    prompt_tool_calls: list[JSONDict],
    prompt_tool_results: list[JSONValue],
    tool_context: MCPToolContext,
    primitives: TurnPrimitives,
    iteration_index: int,
    turn_state_writer: TurnStateWriter,
    next_action_sequence: Callable[[], Awaitable[int]],
    emit_event: Callable[[Event], Awaitable[None]],
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
) -> None:
    for tool_call, tool_result in zip(prompt_tool_calls, prompt_tool_results, strict=True):
        call_id = _resolve_rejected_call_id(tool_call)
        tool_call["id"] = call_id
        should_publish_activity = True
        if should_persist_visible_tool_call_rows(request_context):
            should_publish_activity = await _persist_rejected_tool_call_row(
                tool_call=tool_call,
                tool_result=tool_result,
                tool_context=tool_context,
                request_context=request_context,
                iteration_index=iteration_index,
                database_tool_calls=database_tool_calls,
            )
        if not should_publish_activity:
            continue
        created_event = _build_rejected_tool_created_event(
            tool_call=tool_call,
            tool_context=tool_context,
            primitives=primitives,
            iteration_index=iteration_index,
        )
        activity_sequence = int(await next_action_sequence())
        await turn_state_writer.persist_tool_activity(
            event=created_event,
            activity_sequence=activity_sequence,
            text_length_before=_read_required_nonnegative_int(
                tool_call.get("content_index_before"),
                "content_index_before",
            ),
        )
        await emit_event(created_event)
        completed_event = _build_rejected_tool_completed_event(
            tool_call=tool_call,
            tool_result=tool_result,
            tool_context=tool_context,
            primitives=primitives,
            iteration_index=iteration_index,
        )
        completed_activity_sequence = int(await next_action_sequence())
        await turn_state_writer.persist_tool_activity(
            event=completed_event,
            activity_sequence=completed_activity_sequence,
            text_length_before=_read_required_nonnegative_int(
                tool_call.get("content_index_before"),
                "content_index_before",
            ),
        )
        await emit_event(completed_event)


async def _persist_rejected_tool_call_row(
    *,
    tool_call: JSONDict,
    tool_result: JSONValue,
    tool_context: MCPToolContext,
    request_context: RequestContext,
    iteration_index: int,
    database_tool_calls: DatabaseToolCallsProtocol,
) -> bool:
    call_id = _resolve_rejected_call_id(tool_call)
    now = epoch_ms()
    iteration_request_context = clone_request_context(
        request_context,
        agent_iteration_index=iteration_index,
    )
    create_result = await database_tool_calls.create_tool_call(
        build_canonical_tool_call_request(
            request_context=iteration_request_context,
            tool_context=tool_context,
            call_id=call_id,
            tool_name=str(tool_call.get("name") or "tool"),
            tool_arguments="{}",
            status=TOOL_CALL_STATUS_ERROR,
            sequence_index=_read_required_nonnegative_int(
                tool_call.get("sequence_index"),
                "sequence_index",
            ),
            content_index_before=_read_required_nonnegative_int(
                tool_call.get("content_index_before"),
                "content_index_before",
            ),
            thinking_index_before=_read_required_nonnegative_int(
                tool_call.get("thinking_index_before"),
                "thinking_index_before",
            ),
            thinking_duration_before_ms=_read_optional_nonnegative_int(
                tool_call.get("thinking_duration_before_ms"),
            ),
            collapsed=True,
            error_message=_resolve_error_message(tool_result),
            tool_result=serialize_json_compact_stable(tool_result),
            duration_ms=0,
            created_at_ms=now,
            completed_at_ms=now,
        ),
    )
    return create_result.inserted or create_result.claimed_existing


def _resolve_rejected_call_id(tool_call: JSONDict) -> str:
    call_id = str(tool_call.get("id") or "").strip()
    if call_id:
        return call_id
    return create_prefixed_hex_id("call_rejected")


def _build_rejected_tool_created_event(
    *,
    tool_call: JSONDict,
    tool_context: MCPToolContext,
    primitives: TurnPrimitives,
    iteration_index: int,
) -> ToolCallCreatedEvent:
    return ToolCallCreatedEvent(
        user_id=primitives.user_id,
        conv_id=primitives.conv_id,
        call_id=_resolve_rejected_call_id(tool_call),
        tool_name=str(tool_call.get("name") or "tool"),
        message_index=int(tool_context.message_index),
        sequence_index=_read_required_nonnegative_int(
            tool_call.get("sequence_index"),
            "sequence_index",
        ),
        content_index_before=_read_required_nonnegative_int(
            tool_call.get("content_index_before"),
            "content_index_before",
        ),
        thinking_index_before=_read_required_nonnegative_int(
            tool_call.get("thinking_index_before"),
            "thinking_index_before",
        ),
        thinking_duration_before_ms=_read_optional_nonnegative_int(
            tool_call.get("thinking_duration_before_ms"),
        ),
        tool_arguments="{}",
        turn_id=primitives.turn_id,
        iteration_index=iteration_index,
    )


def _build_rejected_tool_completed_event(
    *,
    tool_call: JSONDict,
    tool_result: JSONValue,
    tool_context: MCPToolContext,
    primitives: TurnPrimitives,
    iteration_index: int,
) -> ToolCallCompletedEvent:
    return ToolCallCompletedEvent(
        user_id=primitives.user_id,
        conv_id=primitives.conv_id,
        call_id=_resolve_rejected_call_id(tool_call),
        tool_name=str(tool_call.get("name") or "tool"),
        status=TOOL_CALL_STATUS_ERROR,
        message_index=int(tool_context.message_index),
        sequence_index=_read_required_nonnegative_int(
            tool_call.get("sequence_index"),
            "sequence_index",
        ),
        content_index_before=_read_required_nonnegative_int(
            tool_call.get("content_index_before"),
            "content_index_before",
        ),
        thinking_index_before=_read_required_nonnegative_int(
            tool_call.get("thinking_index_before"),
            "thinking_index_before",
        ),
        thinking_duration_before_ms=_read_optional_nonnegative_int(
            tool_call.get("thinking_duration_before_ms"),
        ),
        tool_arguments="{}",
        result=tool_result,
        duration_ms=0,
        error_message=_resolve_error_message(tool_result),
        code_diffs=None,
        turn_id=primitives.turn_id,
        iteration_index=iteration_index,
    )


def _resolve_error_message(tool_result: JSONValue) -> str:
    if not isinstance(tool_result, dict):
        return "Tool call rejected before execution."
    error_value = tool_result.get("error")
    if isinstance(error_value, str) and error_value.strip():
        return error_value.strip()
    return serialize_json_compact_stable(tool_result)


def _read_required_nonnegative_int(value: JSONValue, field_name: str) -> int:
    return resolve_required_non_negative_integer(
        value,
        field_name,
        field_label="Rejected tool call",
        exception_type=StateError,
    )


def _read_optional_nonnegative_int(value: JSONValue) -> int | None:
    return coerce_optional_non_negative_int_strict(value)
