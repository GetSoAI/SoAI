"""SoAI - Agent turn noncritical finalization request helpers [backend/features/agent/runtime/turn_lifecycle/noncritical_finalization_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.agent.status_defaults import resolve_agent_turn_terminal_defaults
from core.agent.status_values import (
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_ERROR,
)

__all__ = (
    "AgentTurnNoncriticalFinalizationRequest",
    "build_cancelled_turn_noncritical_finalization_request",
    "build_error_turn_noncritical_finalization_request",
    "build_terminal_turn_noncritical_finalization_request",
)


@dataclass(frozen=True, slots=True)
class AgentTurnNoncriticalFinalizationRequest:
    trace_id: str
    conv_id: str
    user_id: int
    turn_id: str | None
    execution_token: str | None
    status: str
    reached_max_iterations: bool
    error_message: str | None
    error_type: str | None
    iteration_index: int | None
    sequence: int | None
    turn_cancellation_id: str | None
    operation: str
    log_message: str


def build_terminal_turn_noncritical_finalization_request(
    *,
    trace_id: str,
    conv_id: str,
    user_id: int,
    turn_id: str | None,
    execution_token: str | None,
    status: str,
    reached_max_iterations: bool,
    error_message: str | None,
    error_type: str | None,
    operation: str,
    log_message: str,
) -> AgentTurnNoncriticalFinalizationRequest:
    return AgentTurnNoncriticalFinalizationRequest(
        trace_id=trace_id,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        execution_token=execution_token,
        status=status,
        reached_max_iterations=reached_max_iterations,
        error_message=error_message,
        error_type=error_type,
        iteration_index=None,
        sequence=None,
        turn_cancellation_id=None,
        operation=operation,
        log_message=log_message,
    )


def build_error_turn_noncritical_finalization_request(
    *,
    trace_id: str,
    conv_id: str,
    user_id: int,
    turn_id: str | None,
    execution_token: str | None,
    error_message: str,
    error_type: str,
    operation: str,
    log_message: str,
) -> AgentTurnNoncriticalFinalizationRequest:
    return build_terminal_turn_noncritical_finalization_request(
        trace_id=trace_id,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        execution_token=execution_token,
        status=AGENT_TURN_STATUS_ERROR,
        reached_max_iterations=False,
        error_message=error_message,
        error_type=error_type,
        operation=operation,
        log_message=log_message,
    )


def build_cancelled_turn_noncritical_finalization_request(
    *,
    trace_id: str,
    conv_id: str,
    user_id: int,
    turn_id: str | None,
    execution_token: str | None,
    operation: str,
    log_message: str,
) -> AgentTurnNoncriticalFinalizationRequest:
    _, error_message, error_type = resolve_agent_turn_terminal_defaults(AGENT_TURN_STATUS_CANCELLED)
    return build_terminal_turn_noncritical_finalization_request(
        trace_id=trace_id,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        execution_token=execution_token,
        status=AGENT_TURN_STATUS_CANCELLED,
        reached_max_iterations=False,
        error_message=error_message or "Agent turn cancelled.",
        error_type=error_type or AGENT_TURN_STATUS_CANCELLED,
        operation=operation,
        log_message=log_message,
    )
