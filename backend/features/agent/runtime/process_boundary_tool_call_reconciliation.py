"""SoAI - Agent process-boundary tool-call reconciliation [backend/features/agent/runtime/process_boundary_tool_call_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ProcessError, SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from features.agent.runtime.stale_turn_tool_call_finalization import (
    resolve_terminal_root_tool_call_error_message,
    resolve_terminal_root_tool_call_status,
)
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


async def _finalize_subagent_parent_tool_call(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    record: JSONDict,
    logger: LoggerProtocol,
    failures: list[SoAIError] | None,
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
    except TaskCancelledError:
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if failures is None and not isinstance(exception, RECOVERABLE_EXCEPTIONS):
            raise
        failure = ProcessError(
            "Failed to finalize stale subagent parent tool call at process boundary.",
            operation=_OPERATION,
            cause=exception,
            details={
                "conv_id": snapshot.conv_id,
                "turn_id": snapshot.subagent_id,
                "parent_tool_call_id": snapshot.parent_tool_call_id,
            },
        )
        if failures is not None:
            failures.append(failure)
        else:
            log_handled_exception(
                logger,
                exception,
                message=failure.message,
                operation=_OPERATION,
                details=failure.details,
                level="warning",
            )


async def _repair_active_parent_tool_calls_for_terminal_subagents(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    failures: list[SoAIError] | None,
    limit: int,
) -> None:
    records = await database_agent_turn_process_boundary.query_terminal_subagent_turns_with_active_parent_tool_calls(
        limit=limit
    )
    for record in records:
        try:
            await _finalize_subagent_parent_tool_call(
                database_tool_calls=database_tool_calls,
                record=record,
                logger=logger,
                failures=failures,
            )
        except TaskCancelledError:
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if failures is None:
                raise
            failures.append(
                ProcessError(
                    "Failed to reconcile subagent parent tool call at process boundary.",
                    operation=_OPERATION,
                    cause=exception,
                    details={
                        "conv_id": str(record.get("conv_id") or ""),
                        "turn_id": str(record.get("turn_id") or ""),
                        "parent_tool_call_id": str(record.get("parent_tool_call_id") or ""),
                    },
                )
            )


async def _repair_active_tool_calls_for_terminal_root_turns(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    failures: list[SoAIError] | None,
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
                status=resolve_terminal_root_tool_call_status(turn_status),
                error_message=resolve_terminal_root_tool_call_error_message(
                    turn_status,
                    str(record.get("turn_error_message") or ""),
                ),
                completed_at_ms=completed_at_ms,
            )
        except TaskCancelledError:
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if failures is None and not isinstance(exception, RECOVERABLE_EXCEPTIONS):
                raise
            failure = ProcessError(
                "Failed to finalize stale root-turn tool call at process boundary.",
                operation=_OPERATION,
                cause=exception,
                details={
                    "conv_id": str(record.get("conv_id") or ""),
                    "turn_id": str(record.get("turn_id") or ""),
                    "tool_storage_call_id": storage_call_id,
                    "tool_name": str(record.get("tool_name") or ""),
                    "turn_status": turn_status,
                },
            )
            if failures is not None:
                failures.append(failure)
            else:
                log_handled_exception(
                    logger,
                    exception,
                    message=failure.message,
                    operation=_OPERATION,
                    details=failure.details,
                    level="warning",
                )


async def repair_active_tool_calls_for_terminal_turns(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    failures: list[SoAIError] | None,
    limit: int,
) -> None:
    for group_name, repair in (
        ("Subagent Parent Tool Calls", _repair_active_parent_tool_calls_for_terminal_subagents),
        ("Root Turn Tool Calls", _repair_active_tool_calls_for_terminal_root_turns),
    ):
        try:
            await repair(
                database_agent_turn_process_boundary=database_agent_turn_process_boundary,
                database_tool_calls=database_tool_calls,
                logger=logger,
                failures=failures,
                limit=limit,
            )
        except TaskCancelledError:
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if failures is None:
                raise
            failures.append(
                ProcessError(
                    f"Failed to query tool calls at process boundary for {group_name}.",
                    operation=_OPERATION,
                    cause=exception,
                    details={"group": group_name},
                )
            )
