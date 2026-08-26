"""SoAI - Deferred tool call lifecycle persistence [backend/core/tool_calls/deferred_tool_call_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.serialization.json import serialize_json_compact_stable_strict
from core.tool_calls.status_values import TOOL_CALL_STATUS_RUNNING

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tool_calls.deferred_tool_call_row import DeferredToolCallRow
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "OPERATION_DEFERRED_TOOL_CALL_MARK_RUNNING",
    "OPERATION_DEFERRED_TOOL_CALL_PERSIST_TERMINAL",
    "persist_deferred_tool_call_running_state",
    "persist_deferred_tool_call_terminal_state",
)

OPERATION_DEFERRED_TOOL_CALL_MARK_RUNNING = "core.tool_calls.deferred_tool_call.mark_running"
OPERATION_DEFERRED_TOOL_CALL_PERSIST_TERMINAL = (
    "core.tool_calls.deferred_tool_call.persist_terminal"
)


async def persist_deferred_tool_call_running_state(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    trace_id: str,
    call_id: str,
    row: DeferredToolCallRow,
    started_at_ms: int,
) -> None:
    try:
        await database_tool_calls.update_tool_call_result(
            row.storage_call_id,
            status=TOOL_CALL_STATUS_RUNNING,
            tool_result=None,
            error_message=None,
            duration_ms=None,
            started_at_ms=started_at_ms,
            completed_at_ms=None,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_DEFERRED_TOOL_CALL_MARK_RUNNING,
            trace_id=trace_id,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed to mark deferred tool call as running for live updates (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_DEFERRED_TOOL_CALL_MARK_RUNNING,
            level="warning",
            details={"call_id": call_id},
        )


async def persist_deferred_tool_call_terminal_state(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    trace_id: str,
    call_id: str,
    row: DeferredToolCallRow,
    status: str,
    duration_ms: int,
    error_message: str | None,
    completed_at_ms: int,
    result_payload: JSONValue | None,
) -> JSONDict | None:
    try:
        serialized_result = (
            serialize_json_compact_stable_strict(result_payload)
            if result_payload is not None
            else None
        )
        return await database_tool_calls.update_tool_call_result(
            row.storage_call_id,
            status=status,
            tool_result=serialized_result,
            error_message=error_message,
            duration_ms=max(0, int(duration_ms)),
            completed_at_ms=completed_at_ms,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_DEFERRED_TOOL_CALL_PERSIST_TERMINAL,
            trace_id=trace_id,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed to persist deferred tool call terminal state.",
            trace_id=trace_id,
            operation=OPERATION_DEFERRED_TOOL_CALL_PERSIST_TERMINAL,
            level="warning",
            details={"call_id": call_id},
        )
        raise
