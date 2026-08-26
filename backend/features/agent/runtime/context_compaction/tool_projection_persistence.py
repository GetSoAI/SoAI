"""SoAI - Context compaction tool-call projection persistence [backend/features/agent/runtime/context_compaction/tool_projection_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable
from core.tool_calls.canonical_requests import (
    build_canonical_tool_call_request,
    build_canonical_tool_call_storage_id,
    build_pending_collapsed_tool_call_request,
)
from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_PENDING,
    TOOL_CALL_STATUS_RUNNING,
)

if TYPE_CHECKING:
    from core.database.requests import CreateToolCallResult
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONValue

__all__ = (
    "persist_context_compaction_completed_projection",
    "persist_context_compaction_pending_projection",
    "persist_context_compaction_started_projection",
)


def _require_tool_call_inserted_or_claimed(result: CreateToolCallResult, label: str) -> None:
    if not result.inserted and not result.claimed_existing:
        raise StateError(f"{label} tool-call projection row was not claimed.")


async def persist_context_compaction_pending_projection(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    call_id: str,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
    created_at_ms: int,
) -> None:
    create_result = await database_tool_calls.create_tool_call(
        build_pending_collapsed_tool_call_request(
            request_context=request_context,
            tool_context=tool_context,
            call_id=call_id,
            tool_name=CONTEXT_COMPACTION_TOOL_NAME,
            tool_arguments=None,
            status=TOOL_CALL_STATUS_PENDING,
            sequence_index=sequence_index,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
            thinking_duration_before_ms=thinking_duration_before_ms,
            created_at_ms=created_at_ms,
        ),
    )
    if not create_result.inserted:
        raise StateError("Context compaction tool-call projection row already exists.")


async def persist_context_compaction_started_projection(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    call_id: str,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
    started_at_ms: int,
) -> None:
    create_result = await database_tool_calls.create_tool_call(
        build_canonical_tool_call_request(
            request_context=request_context,
            tool_context=tool_context,
            call_id=call_id,
            tool_name=CONTEXT_COMPACTION_TOOL_NAME,
            tool_arguments=None,
            status=TOOL_CALL_STATUS_RUNNING,
            sequence_index=sequence_index,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
            thinking_duration_before_ms=thinking_duration_before_ms,
            collapsed=True,
            started_at_ms=started_at_ms,
            created_at_ms=started_at_ms,
            exclusive_claim=True,
        ),
    )
    _require_tool_call_inserted_or_claimed(create_result, "Context compaction")


async def persist_context_compaction_completed_projection(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    call_id: str,
    status: str,
    result_payload: JSONValue,
    duration_ms: int,
    error_message: str | None,
    completed_at_ms: int,
) -> None:
    storage_call_id = build_canonical_tool_call_storage_id(
        request_context=request_context,
        tool_context=tool_context,
        call_id=call_id,
    )
    persisted = await database_tool_calls.update_tool_call_result(
        storage_call_id,
        status=status,
        tool_result=serialize_json_compact_stable(result_payload),
        error_message=error_message,
        duration_ms=duration_ms,
        completed_at_ms=completed_at_ms,
    )
    if persisted is None:
        raise StateError("Context compaction tool-call projection row was not found.")
