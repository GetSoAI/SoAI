"""SoAI - Initial MCP tool call persistence stages [backend/orchestrator/tool_calls/persistence_initial.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import CreateToolCallRequest, CreateToolCallResult
from core.events.types_system import (
    ToolCallCreatedEvent,
    ToolCallStartedEvent,
)
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.tool_calls.canonical_requests import build_canonical_tool_call_request
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_ERROR,
    TOOL_CALL_STATUS_PENDING,
    TOOL_CALL_STATUS_RUNNING,
)
from orchestrator.tool_calls.persistence import (
    ToolCallChronology,
    ToolCallExecutionRecord,
    ToolCallPersistenceContext,
    publish_tool_call_completed_event_with_raw_arguments_json,
    publish_tool_call_event,
    resolve_tool_arguments_json,
    resolve_tool_call_event_chronology,
)

__all__ = (
    "persist_tool_call_error",
    "persist_tool_call_execution_started",
)

if TYPE_CHECKING:
    from core.types.json import JSONValue


def _resolve_created_chronology(
    record: ToolCallExecutionRecord,
    create_result: CreateToolCallResult | None,
) -> ToolCallChronology:
    persisted = create_result.row if create_result is not None else None
    return resolve_tool_call_event_chronology(persisted, record.chronology)


async def persist_tool_call_error(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    error_message: str,
    duration_ms: int = 0,
    result_payload: JSONValue | None = None,
) -> None:
    now = epoch_ms()
    resolved_arguments_json = resolve_tool_arguments_json(record.arguments_json)
    result_json = (
        serialize_json_compact_stable(result_payload) if result_payload is not None else None
    )
    completed_event_required = True
    if context.persist_visible_rows:
        create_result = await context.database_tool_calls.create_tool_call(
            _build_tool_call_create_request(
                context,
                record,
                resolved_arguments_json=resolved_arguments_json,
                status=TOOL_CALL_STATUS_ERROR,
                terminal_error_message=error_message,
                serialized_tool_result=result_json,
                elapsed_duration_ms=duration_ms,
                execution_started_at_ms=None,
                row_created_at_ms=now,
                terminal_completed_at_ms=now,
                exclusive_claim=False,
            ),
        )
        completed_event_required = create_result.inserted or create_result.claimed_existing
        published_chronology = _resolve_created_chronology(record, create_result)
    else:
        published_chronology = record.chronology
    if not completed_event_required:
        return
    await publish_tool_call_completed_event_with_raw_arguments_json(
        context,
        call_identifier=record.call_identifier,
        tool_name=record.tool_name,
        status=TOOL_CALL_STATUS_ERROR,
        arguments_json=resolved_arguments_json,
        chronology=published_chronology,
        result=result_payload,
        duration_ms=duration_ms,
        error_message=error_message,
    )


async def persist_tool_call_execution_started(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
) -> None:
    now = epoch_ms()
    resolved_arguments_json = resolve_tool_arguments_json(record.arguments_json)
    is_subagent_spawn = record.tool_name == "subagent_spawn"
    status = TOOL_CALL_STATUS_PENDING if is_subagent_spawn else TOOL_CALL_STATUS_RUNNING
    create_result: CreateToolCallResult | None = None
    if context.persist_visible_rows:
        create_result = await context.database_tool_calls.create_tool_call(
            _build_tool_call_create_request(
                context,
                record,
                resolved_arguments_json=resolved_arguments_json,
                status=status,
                terminal_error_message=None,
                serialized_tool_result=None,
                elapsed_duration_ms=0,
                execution_started_at_ms=now,
                row_created_at_ms=now,
                terminal_completed_at_ms=None,
                exclusive_claim=True,
            ),
        )
    published_chronology = _resolve_created_chronology(record, create_result)
    if create_result is None or create_result.inserted:
        await _publish_tool_call_created(
            context,
            record=record,
            chronology=published_chronology,
            resolved_arguments_json=resolved_arguments_json,
        )
    if is_subagent_spawn:
        return
    await _publish_tool_call_started(
        context,
        record=record,
        chronology=published_chronology,
        resolved_arguments_json=resolved_arguments_json,
        started_at_ms=now,
    )


def _build_tool_call_create_request(
    context: ToolCallPersistenceContext,
    record: ToolCallExecutionRecord,
    *,
    resolved_arguments_json: str | None,
    status: str,
    terminal_error_message: str | None,
    serialized_tool_result: str | None,
    elapsed_duration_ms: int,
    execution_started_at_ms: int | None,
    row_created_at_ms: int,
    terminal_completed_at_ms: int | None,
    exclusive_claim: bool,
) -> CreateToolCallRequest:
    return build_canonical_tool_call_request(
        request_context=context.request_context,
        tool_context=context.tool_context,
        call_id=record.call_identifier,
        tool_name=record.tool_name,
        tool_arguments=resolved_arguments_json,
        status=status,
        sequence_index=record.chronology.sequence_index,
        content_index_before=record.chronology.content_index_before,
        thinking_index_before=record.chronology.thinking_index_before,
        thinking_duration_before_ms=record.chronology.thinking_duration_before_ms,
        collapsed=True,
        error_message=terminal_error_message,
        tool_result=serialized_tool_result,
        duration_ms=elapsed_duration_ms,
        started_at_ms=execution_started_at_ms,
        created_at_ms=row_created_at_ms,
        completed_at_ms=terminal_completed_at_ms,
        exclusive_claim=exclusive_claim,
    )


async def _publish_tool_call_created(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    chronology: ToolCallChronology,
    resolved_arguments_json: str | None,
) -> None:
    await publish_tool_call_event(
        context,
        ToolCallCreatedEvent(
            user_id=context.tool_context.user_id,
            conv_id=context.tool_context.conv_id,
            call_id=record.call_identifier,
            tool_name=record.tool_name,
            message_index=context.tool_context.message_index,
            sequence_index=chronology.sequence_index,
            content_index_before=chronology.content_index_before,
            thinking_index_before=chronology.thinking_index_before,
            thinking_duration_before_ms=chronology.thinking_duration_before_ms,
            tool_arguments=resolved_arguments_json,
            turn_id=context.request_context.agent_turn_id,
            iteration_index=context.request_context.agent_iteration_index,
        ),
    )


async def _publish_tool_call_started(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    chronology: ToolCallChronology,
    resolved_arguments_json: str | None,
    started_at_ms: int,
) -> None:
    await publish_tool_call_event(
        context,
        ToolCallStartedEvent(
            user_id=context.tool_context.user_id,
            conv_id=context.tool_context.conv_id,
            call_id=record.call_identifier,
            tool_name=record.tool_name,
            tool_arguments=resolved_arguments_json,
            message_index=context.tool_context.message_index,
            sequence_index=chronology.sequence_index,
            content_index_before=chronology.content_index_before,
            thinking_index_before=chronology.thinking_index_before,
            thinking_duration_before_ms=chronology.thinking_duration_before_ms,
            started_at_ms=started_at_ms,
            turn_id=context.request_context.agent_turn_id,
            iteration_index=context.request_context.agent_iteration_index,
        ),
    )
