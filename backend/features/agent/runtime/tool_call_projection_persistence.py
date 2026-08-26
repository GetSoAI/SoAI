"""SoAI - Agent visible tool-call projection persistence [backend/features/agent/runtime/tool_call_projection_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.tool_calls.canonical_requests import (
    build_canonical_tool_call_storage_id,
    build_pending_collapsed_tool_call_request,
)
from core.tool_calls.chronology import (
    resolve_optional_non_negative_integer,
    resolve_required_non_negative_integer,
)
from core.tool_calls.error_payloads import TOOL_CALL_USER_DENIED_ERROR_MESSAGE
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_ERROR,
    TOOL_CALL_STATUS_PENDING,
)

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "persist_cancelled_visible_tool_call_projection",
    "persist_error_visible_tool_call_projection",
    "persist_pending_visible_tool_call_projection",
    "persist_user_denied_visible_tool_call",
)


def _resolve_required_chronology_field(tool_call: JSONDict, field_name: str) -> int:
    return resolve_required_non_negative_integer(
        tool_call.get(field_name),
        field_name,
        field_label="Tool call",
        exception_type=ValueError,
    )


async def persist_pending_visible_tool_call_projection(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call: JSONDict,
    tool_name: str,
    tool_arguments: str | None,
    created_at_ms: int,
) -> None:
    call_id = str(tool_call.get("id") or "").strip()
    sequence_index = _resolve_required_chronology_field(tool_call, "sequence_index")
    content_index_before = _resolve_required_chronology_field(
        tool_call,
        "content_index_before",
    )
    thinking_index_before = _resolve_required_chronology_field(
        tool_call,
        "thinking_index_before",
    )
    thinking_duration_before_ms = resolve_optional_non_negative_integer(
        tool_call.get("thinking_duration_before_ms"),
        "thinking_duration_before_ms",
        field_label="Tool call",
        exception_type=ValueError,
    )
    await database_tool_calls.create_tool_call(
        build_pending_collapsed_tool_call_request(
            request_context=request_context,
            tool_context=tool_context,
            call_id=call_id,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            status=TOOL_CALL_STATUS_PENDING,
            sequence_index=sequence_index,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
            thinking_duration_before_ms=thinking_duration_before_ms,
            created_at_ms=created_at_ms,
        ),
    )


async def persist_cancelled_visible_tool_call_projection(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call: JSONDict,
    error_message: str,
) -> None:
    await _persist_terminal_visible_tool_call_projection(
        database_tool_calls=database_tool_calls,
        request_context=request_context,
        tool_context=tool_context,
        tool_call=tool_call,
        status=TOOL_CALL_STATUS_CANCELLED,
        code="cancelled",
        error_message=error_message,
    )


async def persist_error_visible_tool_call_projection(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call: JSONDict,
    error_message: str,
) -> None:
    await _persist_terminal_visible_tool_call_projection(
        database_tool_calls=database_tool_calls,
        request_context=request_context,
        tool_context=tool_context,
        tool_call=tool_call,
        status=TOOL_CALL_STATUS_ERROR,
        code="server_error",
        error_message=error_message,
    )


async def _persist_terminal_visible_tool_call_projection(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call: JSONDict,
    status: str,
    code: str,
    error_message: str,
) -> None:
    call_id = str(tool_call.get("id") or "").strip()
    storage_call_id = build_canonical_tool_call_storage_id(
        request_context=request_context,
        tool_context=tool_context,
        call_id=call_id,
    )
    now = epoch_ms()
    persisted = await database_tool_calls.update_tool_call_result(
        storage_call_id,
        status=status,
        tool_result=serialize_json_compact_stable(
            {
                "error": error_message,
                "code": code,
            },
        ),
        error_message=error_message,
        duration_ms=0,
        completed_at_ms=now,
    )
    if persisted is None:
        raise StateError("Visible tool-call approval projection row was not found.")


async def persist_user_denied_visible_tool_call(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call: JSONDict,
    result_payload: JSONValue,
) -> None:
    call_id = str(tool_call.get("id") or "").strip()
    storage_call_id = build_canonical_tool_call_storage_id(
        request_context=request_context,
        tool_context=tool_context,
        call_id=call_id,
    )
    now = epoch_ms()
    persisted = await database_tool_calls.update_tool_call_result(
        storage_call_id,
        status=TOOL_CALL_STATUS_ERROR,
        tool_result=serialize_json_compact_stable(result_payload),
        error_message=TOOL_CALL_USER_DENIED_ERROR_MESSAGE,
        duration_ms=0,
        completed_at_ms=now,
    )
    if persisted is None:
        raise StateError("Visible tool-call approval projection row was not found.")
