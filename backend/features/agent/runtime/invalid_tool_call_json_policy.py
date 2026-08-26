"""SoAI - Invalid tool-call JSON retry policy [backend/features/agent/runtime/invalid_tool_call_json_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.model_output_contract_errors import MODEL_OUTPUT_CONTRACT_ERROR_CODE
from features.agent.runtime.turn_iteration_policy_decisions import (
    build_retry_required_visible_output_decision,
    build_terminal_invalid_tool_call_json_contract_decision,
)
from features.agent.runtime.turn_iteration_policy_messages import (
    build_invalid_tool_call_json_final_answer_message,
    build_invalid_tool_call_json_repair_message,
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

__all__ = ("decide_invalid_tool_call_json_action",)


def decide_invalid_tool_call_json_action(
    *,
    config: TurnIterationPolicyConfig,
    state: TurnIterationPolicyState,
    iteration_index: int,
    output_publication_mode: AgentOutputPublicationMode,
) -> TurnIterationDecision:
    if state.invalid_tool_call_json_retries < config.max_invalid_tool_call_json_retries:
        if is_next_iteration_blocked(
            iteration_index=iteration_index,
            max_iterations=config.max_iterations,
        ):
            return build_terminal_invalid_tool_call_json_contract_decision(
                state=state,
                error_message=(
                    "Agent turn failed because the model produced invalid tool-call output "
                    "without enough remaining iterations to repair it."
                ),
                error_type=MODEL_OUTPUT_CONTRACT_ERROR_CODE,
                next_output_publication_mode=output_publication_mode,
            )
        next_retry_count = state.invalid_tool_call_json_retries + 1
        suppress_tools = next_retry_count >= config.max_invalid_tool_call_json_retries
        return build_retry_required_visible_output_decision(
            next_state=copy_turn_iteration_policy_state(
                state,
                invalid_tool_call_json_retries=next_retry_count,
            ),
            retry_message=(
                build_invalid_tool_call_json_final_answer_message()
                if suppress_tools
                else build_invalid_tool_call_json_repair_message()
            ),
            suppress_tools_for_next_iteration=suppress_tools,
            next_output_publication_mode=output_publication_mode,
        )
    return build_terminal_invalid_tool_call_json_contract_decision(
        state=state,
        error_message=(
            "Agent turn failed because the model repeatedly produced invalid tool-call JSON."
        ),
        error_type=MODEL_OUTPUT_CONTRACT_ERROR_CODE,
        next_output_publication_mode=output_publication_mode,
    )
