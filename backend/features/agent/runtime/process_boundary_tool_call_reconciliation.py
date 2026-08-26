"""SoAI - Agent process-boundary tool-call reconciliation [backend/features/agent/runtime/process_boundary_tool_call_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_ERROR,
)
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_ERROR,
)
from core.validation.integers import is_strict_int
from features.agent.subagents.parent_tool_call_persistence import (
    build_terminal_tool_result,
    resolve_parent_tool_call_error_message,
    resolve_parent_tool_call_status,
)
from features.agent.subagents.parent_tool_call_update_models import (
    build_live_subagent_record,
    build_subagent_parent_tool_result,
)
from features.agent.subagents.snapshots import build_subagent_snapshot

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import (
        DatabaseAgentTurnProcessBoundaryProtocol,
    )
    from core.logging.protocols import LoggerProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = ("repair_active_tool_calls_for_terminal_turns",)

_OPERATION = "features.agent.runtime.reconcile_tool_call_at_process_boundary"


def _resolve_terminal_root_tool_call_status(turn_status: str) -> str:
    normalized_status = str(turn_status or "").strip()
    if normalized_status in {AGENT_TURN_STATUS_CANCELLED, AGENT_TURN_STATUS_ABANDONED}:
        return TOOL_CALL_STATUS_CANCELLED
    return TOOL_CALL_STATUS_ERROR


def _resolve_terminal_root_tool_call_error_message(record: JSONDict) -> str:
    turn_status = str(record.get("turn_status") or "").strip()
    turn_message = str(record.get("turn_error_message") or "").strip()
    if turn_status == AGENT_TURN_STATUS_CANCELLED:
        return turn_message or "Tool call cancelled because the agent turn was cancelled."
    if turn_status == AGENT_TURN_STATUS_ABANDONED:
        return turn_message or "Tool call cancelled because the agent turn was abandoned."
    if turn_status == AGENT_TURN_STATUS_ERROR:
        return turn_message or "Tool call failed because the agent turn ended with an error."
    return (
        turn_message or "Tool call did not finish before the agent turn reached a terminal state."
    )


async def _finalize_subagent_parent_tool_call_noncritical(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    record: JSONDict,
    logger: LoggerProtocol,
) -> None:
    snapshot = build_subagent_snapshot(record)
    if snapshot is None or snapshot.finished_at_ms is None:
        return
    status = resolve_parent_tool_call_status(snapshot.status)
    error_message = resolve_parent_tool_call_error_message(
        parent_status=status,
        subagent_status=snapshot.status,
        error_message=snapshot.error_message,
    )
    subagent_record = build_live_subagent_record(
        snapshot=snapshot,
        result_text=snapshot.result_text,
        token_usage=snapshot.token_usage,
    )
    result_payload = build_subagent_parent_tool_result(
        subagent_record=subagent_record,
        child_tool_calls=[],
        text_blocks=[],
    )
    tool_result = build_terminal_tool_result(
        result_payload=result_payload,
        token_usage=snapshot.token_usage,
    )
    try:
        await database_tool_calls.finalize_subagent_parent_tool_call_if_unfinished(
            conv_id=snapshot.conv_id,
            parent_tool_call_id=snapshot.parent_tool_call_id,
            parent_turn_id=snapshot.parent_turn_id,
            parent_iteration_index=snapshot.parent_iteration_index,
            status=status,
            error_message=error_message,
            tool_result=serialize_json_compact_stable_strict(tool_result),
            duration_ms=max(0, int(snapshot.finished_at_ms) - int(snapshot.started_at_ms)),
            completed_at_ms=int(snapshot.finished_at_ms),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to finalize stale subagent parent tool call at process boundary.",
            operation=_OPERATION,
            details={
                "conv_id": snapshot.conv_id,
                "turn_id": snapshot.subagent_id,
                "parent_tool_call_id": snapshot.parent_tool_call_id,
                "parent_turn_id": snapshot.parent_turn_id,
                "status": status,
                "error_message": snapshot.error_message,
            },
            level="warning",
        )


async def _repair_active_parent_tool_calls_for_terminal_subagents(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    limit: int,
) -> None:
    records = await database_agent_turn_process_boundary.query_terminal_subagent_turns_with_active_parent_tool_calls(
        limit=limit,
    )
    for record in records:
        await _finalize_subagent_parent_tool_call_noncritical(
            database_tool_calls=database_tool_calls,
            record=record,
            logger=logger,
        )


async def _repair_active_tool_calls_for_terminal_root_turns(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    limit: int,
) -> None:
    records = await database_agent_turn_process_boundary.query_terminal_root_turn_active_tool_calls(
        limit=limit,
    )
    for record in records:
        storage_call_id = str(record.get("tool_storage_call_id") or "").strip()
        if not storage_call_id:
            continue
        turn_status = str(record.get("turn_status") or "").strip()
        completed_value = record.get("turn_finished_at_ms")
        completed_at_ms = completed_value if is_strict_int(completed_value) else epoch_ms()
        try:
            await database_tool_calls.finalize_tool_call_if_unfinished(
                storage_call_id,
                status=_resolve_terminal_root_tool_call_status(turn_status),
                error_message=_resolve_terminal_root_tool_call_error_message(record),
                completed_at_ms=completed_at_ms,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to finalize stale root-turn tool call at process boundary.",
                operation=_OPERATION,
                details={
                    "conv_id": str(record.get("conv_id") or ""),
                    "turn_id": str(record.get("turn_id") or ""),
                    "tool_storage_call_id": storage_call_id,
                    "tool_name": str(record.get("tool_name") or ""),
                    "turn_status": turn_status,
                },
                level="warning",
            )


async def repair_active_tool_calls_for_terminal_turns(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    limit: int,
) -> None:
    await _repair_active_parent_tool_calls_for_terminal_subagents(
        database_agent_turn_process_boundary=database_agent_turn_process_boundary,
        database_tool_calls=database_tool_calls,
        logger=logger,
        limit=limit,
    )
    await _repair_active_tool_calls_for_terminal_root_turns(
        database_agent_turn_process_boundary=database_agent_turn_process_boundary,
        database_tool_calls=database_tool_calls,
        logger=logger,
        limit=limit,
    )
