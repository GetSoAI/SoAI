"""SoAI - Agent turn noncritical finalization [backend/features/agent/runtime/turn_lifecycle/finalize.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.turn_record_fields import read_turn_int, read_turn_optional_text
from core.agent.turn_state_record_rewrites import (
    build_terminal_turn_state_request_from_record,
)
from core.agent.turn_write_conflicts import AgentTurnStaleProgressError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.epoch import epoch_ms
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    AgentTurnNoncriticalFinalizationRequest,
)
from features.agent.runtime.turn_lifecycle.noncritical_logging import (
    build_noncritical_turn_details,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "finalize_running_turn_noncritical",
    "resolve_exact_turn_noncritical",
)

OPERATION_FEATURES_AGENT_RUNTIME_TURN_STATE_NONCRITICAL_FINALIZE_RUNNING_TURN_NONCRITICAL = (
    "features.agent.runtime.turn_state_noncritical.finalize_running_turn_noncritical"
)
OPERATION_FEATURES_AGENT_RUNTIME_TURN_STATE_NONCRITICAL_RESOLVE_EXACT_TURN_NONCRITICAL = (
    "features.agent.runtime.turn_state_noncritical.resolve_exact_turn_noncritical"
)
_NONCRITICAL_FINALIZE_MAX_STALE_RETRIES = 3


def _resolve_noncritical_iteration_index(
    request_iteration_index: int | None,
    persisted_iteration_index: int,
) -> int:
    if request_iteration_index is not None and request_iteration_index >= 0:
        return max(request_iteration_index, persisted_iteration_index)
    return persisted_iteration_index


def _resolve_noncritical_sequence(request_sequence: int | None, persisted_sequence: int) -> int:
    if request_sequence is not None and request_sequence >= 0:
        return max(request_sequence, persisted_sequence)
    return persisted_sequence


async def resolve_exact_turn_noncritical(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    logger: LoggerProtocol,
    trace_id: str,
    conv_id: str,
    user_id: int,
    turn_id: str | None,
    request_id: str,
    operation: str,
    log_message: str,
) -> JSONDict | None:
    normalized_turn_id = turn_id.strip() if turn_id is not None else ""
    if not normalized_turn_id or user_id <= 0:
        return None
    try:
        return await database_agent_turns.get_turn(
            conv_id=conv_id,
            user_id=user_id,
            turn_id=normalized_turn_id,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to resolve exact agent turn state (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_FEATURES_AGENT_RUNTIME_TURN_STATE_NONCRITICAL_RESOLVE_EXACT_TURN_NONCRITICAL,
            level="debug",
            details={
                "conv_id": conv_id,
                "request_id": request_id,
                "turn_id": normalized_turn_id,
                "context_message": log_message,
            },
        )
        return None


async def finalize_running_turn_noncritical(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    logger: LoggerProtocol,
    request: AgentTurnNoncriticalFinalizationRequest,
) -> None:
    normalized_turn_id = request.turn_id.strip() if request.turn_id is not None else ""
    normalized_execution_token = (
        request.execution_token.strip() if request.execution_token is not None else ""
    )
    if not normalized_turn_id or not normalized_execution_token or request.user_id <= 0:
        return
    try:
        attempt = 0
        while attempt < _NONCRITICAL_FINALIZE_MAX_STALE_RETRIES:
            turn_record = await database_agent_turns.get_turn(
                conv_id=request.conv_id,
                user_id=request.user_id,
                turn_id=normalized_turn_id,
            )
            if not isinstance(turn_record, dict):
                return
            persisted_status = str(turn_record.get("status") or "").strip()
            persisted_execution_token = str(turn_record.get("execution_token") or "").strip()
            if persisted_status != AGENT_TURN_STATUS_RUNNING:
                return
            if persisted_execution_token != normalized_execution_token:
                return
            now = epoch_ms()
            persisted_iteration_index = max(0, read_turn_int(turn_record, "iteration_index") or 0)
            persisted_sequence = max(0, read_turn_int(turn_record, "sequence") or 0)
            resolved_iteration_index = _resolve_noncritical_iteration_index(
                request.iteration_index,
                persisted_iteration_index,
            )
            resolved_sequence = _resolve_noncritical_sequence(
                request.sequence,
                persisted_sequence,
            )
            resolved_turn_cancellation_id = (
                request.turn_cancellation_id.strip()
                if request.turn_cancellation_id is not None and request.turn_cancellation_id.strip()
                else read_turn_optional_text(turn_record, "turn_cancellation_id")
            )
            write_request = build_terminal_turn_state_request_from_record(
                record=turn_record,
                execution_token=normalized_execution_token,
                status=request.status,
                iteration_index=resolved_iteration_index,
                sequence=resolved_sequence,
                turn_cancellation_id=resolved_turn_cancellation_id,
                active_inference_cancellation_id=None,
                reached_max_iterations=request.reached_max_iterations,
                error_message=request.error_message,
                error_type=request.error_type,
                updated_at_ms=now,
                finished_at_ms=now,
            )
            try:
                await database_agent_turns.write_turn_state(write_request)
                return
            except AgentTurnStaleProgressError:
                attempt += 1
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=request.operation)
        log_exception(
            logger,
            coerced,
            message=request.log_message,
            trace_id=request.trace_id,
            operation=OPERATION_FEATURES_AGENT_RUNTIME_TURN_STATE_NONCRITICAL_FINALIZE_RUNNING_TURN_NONCRITICAL,
            level="warning",
            details=build_noncritical_turn_details(
                conv_id=request.conv_id,
                turn_id=normalized_turn_id,
                context_message=request.log_message,
                request_id=None,
            ),
        )
