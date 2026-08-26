"""SoAI - Shared turn iteration decision builders [backend/features/agent/runtime/turn_iteration_policy_decisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.status_values import (
    AGENT_TURN_STATUS_ERROR,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)
from core.types.json import JSONDict
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
    TurnIterationAction,
    TurnIterationDecision,
    TurnIterationPolicyState,
)

__all__ = (
    "build_retry_required_visible_output_decision",
    "build_terminal_empty_response_decision",
    "build_terminal_invalid_tool_call_json_contract_decision",
    "build_terminal_max_iterations_decision",
)

_EMPTY_RESPONSE_ERROR_TYPE = "empty_response"
_EMPTY_RESPONSE_ERROR_MESSAGE = "Agent turn completed without producing assistant output."


def build_terminal_empty_response_decision(
    *,
    state: TurnIterationPolicyState,
    next_output_publication_mode: AgentOutputPublicationMode,
) -> TurnIterationDecision:
    return TurnIterationDecision(
        action=TurnIterationAction.TERMINAL_EMPTY_RESPONSE,
        next_state=state,
        retry_message=None,
        reached_max_iterations=False,
        terminal_status=AGENT_TURN_STATUS_ERROR,
        terminal_error_message=_EMPTY_RESPONSE_ERROR_MESSAGE,
        terminal_error_type=_EMPTY_RESPONSE_ERROR_TYPE,
        next_output_publication_mode=next_output_publication_mode,
    )


def build_retry_required_visible_output_decision(
    *,
    next_state: TurnIterationPolicyState,
    retry_message: JSONDict,
    suppress_tools_for_next_iteration: bool,
    next_output_publication_mode: AgentOutputPublicationMode,
) -> TurnIterationDecision:
    return TurnIterationDecision(
        action=TurnIterationAction.RETRY_REQUIRED_VISIBLE_OUTPUT,
        next_state=next_state,
        retry_message=retry_message,
        reached_max_iterations=False,
        terminal_status=None,
        terminal_error_message=None,
        terminal_error_type=None,
        next_output_publication_mode=next_output_publication_mode,
        suppress_tools_for_next_iteration=suppress_tools_for_next_iteration,
    )


def build_terminal_invalid_tool_call_json_contract_decision(
    *,
    state: TurnIterationPolicyState,
    error_message: str,
    error_type: str,
    next_output_publication_mode: AgentOutputPublicationMode,
) -> TurnIterationDecision:
    return TurnIterationDecision(
        action=TurnIterationAction.TERMINAL_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION,
        next_state=state,
        retry_message=None,
        reached_max_iterations=False,
        terminal_status=AGENT_TURN_STATUS_ERROR,
        terminal_error_message=error_message,
        terminal_error_type=error_type,
        next_output_publication_mode=next_output_publication_mode,
    )


def build_terminal_max_iterations_decision(
    *,
    state: TurnIterationPolicyState,
    next_output_publication_mode: AgentOutputPublicationMode,
) -> TurnIterationDecision:
    return TurnIterationDecision(
        action=TurnIterationAction.TERMINAL_MAX_ITERATIONS,
        next_state=state,
        retry_message=None,
        reached_max_iterations=True,
        terminal_status=AGENT_TURN_STATUS_MAX_ITERATIONS,
        terminal_error_message=None,
        terminal_error_type=None,
        next_output_publication_mode=next_output_publication_mode,
    )
