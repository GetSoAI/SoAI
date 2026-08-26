"""SoAI - Terminal MCP tool call persistence stages [backend/orchestrator/tool_calls/persistence_terminal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.assistant_timeline.tool_result_truncation import (
    truncate_tool_result_payload_for_timeline,
)
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.tool_calls.file_content_previews import resolve_tool_activity_code_diffs
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
    is_terminal_tool_call_status,
)
from core.types.json import JSONValue
from orchestrator.tool_calls.persistence import (
    ToolCallExecutionRecord,
    ToolCallPersistenceContext,
    publish_tool_call_completed_event_with_raw_arguments_json,
    resolve_tool_call_event_chronology,
)

__all__ = (
    "persist_tool_call_cancelled",
    "persist_tool_call_completed",
    "persist_tool_call_exception_result",
)


async def _persist_terminal_tool_call(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    status: str,
    result_payload: JSONValue,
    duration_ms: int,
    error_message: str | None,
    code_diffs: JSONValue | None = None,
) -> None:
    completed_at_ms = epoch_ms()
    published_status = status
    published_result = truncate_tool_result_payload_for_timeline(result_payload)
    published_error_message = error_message
    published_duration_ms: int | None = duration_ms
    published_code_diffs = resolve_tool_activity_code_diffs(record.tool_name, result_payload)
    if published_code_diffs is None:
        published_code_diffs = resolve_tool_activity_code_diffs(
            record.tool_name,
            {"code_diffs": code_diffs},
        )
    published_chronology = record.chronology
    result_json = serialize_json_compact_stable(result_payload)
    if context.persist_visible_rows:
        persisted = await context.database_tool_calls.update_tool_call_result(
            record.storage_call_identifier,
            status=status,
            tool_result=result_json,
            error_message=error_message,
            duration_ms=duration_ms,
            completed_at_ms=completed_at_ms,
        )
        if isinstance(persisted, dict):
            published_chronology = resolve_tool_call_event_chronology(
                persisted,
                record.chronology,
            )
            persisted_status_value = persisted.get("status")
            persisted_status = (
                persisted_status_value.strip().lower()
                if isinstance(persisted_status_value, str)
                else ""
            )
            if is_terminal_tool_call_status(persisted_status):
                persisted_result = persisted.get("result")
                persisted_error = persisted.get("error")
                persisted_duration = persisted.get("duration_ms")
                published_status = persisted_status
                published_result = truncate_tool_result_payload_for_timeline(persisted_result)
                published_error_message = (
                    persisted_error.strip() if isinstance(persisted_error, str) else None
                )
                published_duration_ms = (
                    persisted_duration
                    if isinstance(persisted_duration, int)
                    and not isinstance(persisted_duration, bool)
                    else None
                )
                published_code_diffs = resolve_tool_activity_code_diffs(
                    record.tool_name,
                    persisted_result,
                )
    await publish_tool_call_completed_event_with_raw_arguments_json(
        context,
        call_identifier=record.call_identifier,
        tool_name=record.tool_name,
        status=published_status,
        arguments_json=record.arguments_json,
        chronology=published_chronology,
        result=published_result,
        duration_ms=published_duration_ms,
        error_message=published_error_message,
        code_diffs=published_code_diffs,
    )


def _extract_code_diffs_payload(result_payload: JSONValue) -> JSONValue | None:
    if not isinstance(result_payload, dict):
        return None
    return result_payload.get("code_diffs")


async def persist_tool_call_completed(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    result_payload: JSONValue,
    duration_ms: int,
) -> None:
    await _persist_terminal_tool_call(
        context,
        record=record,
        status=TOOL_CALL_STATUS_COMPLETED,
        result_payload=result_payload,
        duration_ms=duration_ms,
        error_message=None,
        code_diffs=_extract_code_diffs_payload(result_payload),
    )


async def persist_tool_call_cancelled(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    result_payload: JSONValue,
    duration_ms: int,
    error_message: str,
) -> None:
    await _persist_terminal_tool_call(
        context,
        record=record,
        status=TOOL_CALL_STATUS_CANCELLED,
        result_payload=result_payload,
        duration_ms=duration_ms,
        error_message=error_message,
    )


async def persist_tool_call_exception_result(
    context: ToolCallPersistenceContext,
    *,
    record: ToolCallExecutionRecord,
    result_payload: JSONValue,
    duration_ms: int,
    error_message: str,
) -> None:
    await _persist_terminal_tool_call(
        context,
        record=record,
        status=TOOL_CALL_STATUS_ERROR,
        result_payload=result_payload,
        duration_ms=duration_ms,
        error_message=error_message,
        code_diffs=_extract_code_diffs_payload(result_payload),
    )
