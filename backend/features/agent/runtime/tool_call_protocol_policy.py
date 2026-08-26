"""SoAI - Tool-call protocol retry policy [backend/features/agent/runtime/tool_call_protocol_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.model_output_contract_errors import MODEL_OUTPUT_CONTRACT_ERROR_CODE
from core.types.json import JSONDict
from features.agent.runtime.tool_call_protocol_validation import (
    ToolCallProtocolViolation,
)
from features.agent.runtime.turn_iteration_policy_decisions import (
    build_retry_required_visible_output_decision,
    build_terminal_invalid_tool_call_json_contract_decision,
    build_terminal_max_iterations_decision,
)
from features.agent.runtime.turn_iteration_policy_messages import (
    build_tool_call_protocol_final_answer_message,
    build_tool_call_protocol_repair_message,
    build_tool_call_protocol_strategy_message,
)
from features.agent.runtime.turn_iteration_policy_state import (
    copy_turn_iteration_policy_state,
)
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
    TurnIterationDecision,
    TurnIterationPolicyConfig,
    TurnIterationPolicyState,
    is_next_iteration_blocked,
)

__all__ = ("decide_tool_call_protocol_action",)


def decide_tool_call_protocol_action(
    *,
    config: TurnIterationPolicyConfig,
    state: TurnIterationPolicyState,
    iteration_index: int,
    violation: ToolCallProtocolViolation,
    output_publication_mode: AgentOutputPublicationMode,
) -> TurnIterationDecision:
    if state.tool_call_protocol_retry_signature == violation.signature:
        current_retry_count = state.tool_call_protocol_retries
    else:
        current_retry_count = 0
    if current_retry_count < config.max_tool_call_protocol_retries:
        if is_next_iteration_blocked(
            iteration_index=iteration_index,
            max_iterations=config.max_iterations,
        ):
            return build_terminal_max_iterations_decision(
                state=state,
                next_output_publication_mode=output_publication_mode,
            )
        next_retry_count = current_retry_count + 1
        suppress_tools = next_retry_count >= config.max_tool_call_protocol_retries
        return build_retry_required_visible_output_decision(
            next_state=copy_turn_iteration_policy_state(
                state,
                tool_call_protocol_retries=next_retry_count,
                tool_call_protocol_retry_signature=violation.signature,
            ),
            retry_message=_build_retry_message(
                violation=violation,
                retry_count=next_retry_count,
                suppress_tools=suppress_tools,
            ),
            suppress_tools_for_next_iteration=suppress_tools,
            next_output_publication_mode=output_publication_mode,
        )
    return build_terminal_invalid_tool_call_json_contract_decision(
        state=state,
        error_message=(
            "Agent turn failed because the model repeatedly produced invalid tool-call protocol "
            "output."
        ),
        error_type=MODEL_OUTPUT_CONTRACT_ERROR_CODE,
        next_output_publication_mode=output_publication_mode,
    )


def _build_retry_message(
    *,
    violation: ToolCallProtocolViolation,
    retry_count: int,
    suppress_tools: bool,
) -> JSONDict:
    if suppress_tools:
        return build_tool_call_protocol_final_answer_message(
            tool_name=violation.tool_name,
            error_message=violation.error_message,
            received_argument_type=violation.received_argument_type,
        )
    if retry_count >= 2:
        return build_tool_call_protocol_strategy_message(
            tool_name=violation.tool_name,
            error_message=violation.error_message,
            received_argument_type=violation.received_argument_type,
        )
    return build_tool_call_protocol_repair_message(
        tool_name=violation.tool_name,
        error_message=violation.error_message,
        received_argument_type=violation.received_argument_type,
    )
