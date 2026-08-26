"""SoAI - MCP tool call persistence context and identity [backend/orchestrator/tool_calls/persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_system import ToolCallCompletedEvent
from core.logging.protocols import LoggerProtocol
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tool_calls.chronology import resolve_tool_call_chronology_fields
from core.tool_calls.protocols import DatabaseToolCallsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ToolCallChronology",
    "ToolCallExecutionRecord",
    "ToolCallPersistenceContext",
    "build_tool_call_completed_event",
    "publish_tool_call_completed_event",
    "publish_tool_call_completed_event_with_raw_arguments_json",
    "publish_tool_call_event",
    "resolve_tool_arguments_json",
    "resolve_tool_call_event_chronology",
)

OPERATION_PUBLISH_TOOL_CALL_EVENT = "orchestrator.tool_calls.publish_tool_call_event"


@dataclass(frozen=True, slots=True)
class ToolCallPersistenceContext:
    database_tool_calls: DatabaseToolCallsProtocol
    event_bus: EventBusProtocol | None
    logger: LoggerProtocol
    request_context: RequestContext
    tool_context: MCPToolContext
    persist_visible_rows: bool
    publish_events: bool


@dataclass(frozen=True, slots=True)
class ToolCallChronology:
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ToolCallExecutionRecord:
    storage_call_identifier: str
    call_identifier: str
    tool_name: str
    arguments_json: str | None
    chronology: ToolCallChronology


def resolve_tool_arguments_json(arguments_json: str | None) -> str:
    if isinstance(arguments_json, str) and arguments_json.strip():
        return arguments_json
    return "{}"


def resolve_tool_call_event_chronology(
    persisted: JSONDict | None,
    fallback: ToolCallChronology,
) -> ToolCallChronology:
    if persisted is None:
        return fallback
    chronology = resolve_tool_call_chronology_fields(
        persisted,
        field_label="Persisted tool call",
    )
    return ToolCallChronology(
        sequence_index=chronology.sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
        thinking_duration_before_ms=chronology.thinking_duration_before_ms,
    )


async def publish_tool_call_event(
    context: ToolCallPersistenceContext,
    event_payload: Event,
) -> None:
    if (not context.publish_events) or context.event_bus is None:
        return
    try:
        await context.event_bus.publish(event_payload)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_PUBLISH_TOOL_CALL_EVENT,
        )
        log_exception(
            context.logger,
            coerced,
            message="Tool-call event publication failed.",
            operation=OPERATION_PUBLISH_TOOL_CALL_EVENT,
            level="warning",
        )


def build_tool_call_completed_event(
    context: ToolCallPersistenceContext,
    *,
    call_identifier: str,
    tool_name: str,
    tool_arguments: str,
    chronology: ToolCallChronology,
    status: str,
    result: JSONValue | None,
    duration_ms: int | None,
    error_message: str | None,
    code_diffs: list[JSONDict] | None = None,
) -> ToolCallCompletedEvent:
    return ToolCallCompletedEvent(
        user_id=context.tool_context.user_id,
        conv_id=context.tool_context.conv_id,
        call_id=call_identifier,
        tool_name=tool_name,
        status=status,
        message_index=context.tool_context.message_index,
        sequence_index=chronology.sequence_index,
        content_index_before=chronology.content_index_before,
        thinking_index_before=chronology.thinking_index_before,
        thinking_duration_before_ms=chronology.thinking_duration_before_ms,
        tool_arguments=tool_arguments,
        result=result,
        duration_ms=duration_ms,
        error_message=error_message,
        code_diffs=code_diffs,
        turn_id=context.request_context.agent_turn_id,
        iteration_index=context.request_context.agent_iteration_index,
    )


async def publish_tool_call_completed_event(
    context: ToolCallPersistenceContext,
    *,
    call_identifier: str,
    tool_name: str,
    status: str,
    tool_arguments: str,
    chronology: ToolCallChronology,
    result: JSONValue | None,
    duration_ms: int | None,
    error_message: str | None,
    code_diffs: list[JSONDict] | None = None,
) -> None:
    await publish_tool_call_event(
        context,
        build_tool_call_completed_event(
            context,
            call_identifier=call_identifier,
            tool_name=tool_name,
            status=status,
            tool_arguments=tool_arguments,
            chronology=chronology,
            result=result,
            duration_ms=duration_ms,
            error_message=error_message,
            code_diffs=code_diffs,
        ),
    )


async def publish_tool_call_completed_event_with_raw_arguments_json(
    context: ToolCallPersistenceContext,
    *,
    call_identifier: str,
    tool_name: str,
    status: str,
    arguments_json: str | None,
    chronology: ToolCallChronology,
    result: JSONValue | None,
    duration_ms: int | None,
    error_message: str | None,
    code_diffs: list[JSONDict] | None = None,
) -> str:
    resolved_arguments_json = resolve_tool_arguments_json(arguments_json)
    await publish_tool_call_completed_event(
        context,
        call_identifier=call_identifier,
        tool_name=tool_name,
        status=status,
        tool_arguments=resolved_arguments_json,
        chronology=chronology,
        result=result,
        duration_ms=duration_ms,
        error_message=error_message,
        code_diffs=code_diffs,
    )
    return resolved_arguments_json
