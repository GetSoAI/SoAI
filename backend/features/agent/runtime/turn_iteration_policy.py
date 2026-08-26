"""SoAI - Agent turn iteration policy decisions [backend/features/agent/runtime/turn_iteration_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.status_values import AGENT_TURN_STATUS_ERROR
from core.preview_contract.preview_contract import (
    PREVIEW_CONTRACT_VIOLATION_CODE,
    PREVIEW_CONTRACT_VIOLATION_PUBLIC_MESSAGE,
)
from core.types.json import JSONDict
from features.agent.runtime.invalid_tool_call_json_policy import (
    decide_invalid_tool_call_json_action,
)
from features.agent.runtime.output_publication_policy import (
    resolve_next_output_publication_mode,
)
from features.agent.runtime.turn_empty_output_policy import (
    is_empty_assistant_output,
    should_retry_empty_output,
    should_retry_empty_output_silently,
)
from features.agent.runtime.turn_iteration_policy_decisions import (
    build_terminal_empty_response_decision,
    build_terminal_max_iterations_decision,
)
from features.agent.runtime.turn_iteration_policy_messages import (
    build_finish_reason_length_continue_message,
    build_required_visible_output_message,
    build_tool_sequence_contract_repair_message,
)
from features.agent.runtime.turn_iteration_policy_state import (
    copy_turn_iteration_policy_state,
)
from features.agent.runtime.turn_iteration_policy_types import (
    FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION,
    FINISH_REASON_TOOL_SEQUENCE_CONTRACT_VIOLATION,
    AgentOutputPublicationMode,
    TurnIterationAction,
    TurnIterationDecision,
    TurnIterationPolicyConfig,
    TurnIterationPolicyState,
    is_next_iteration_blocked,
)
from features.api.runtime.preview_contract_output_validation import (
    PreviewContractOutputValidationResult,
)
from features.api.runtime.preview_contract_retry import (
    build_preview_contract_retry_message,
)

__all__ = ("decide_post_inference_action",)


def decide_post_inference_action(
    *,
    config: TurnIterationPolicyConfig,
    state: TurnIterationPolicyState,
    iteration_index: int,
    tool_calls: list[JSONDict],
    assistant_text: str | None,
    finish_reason: str | None,
    current_output_publication_mode: AgentOutputPublicationMode,
    preview_contract_validation: PreviewContractOutputValidationResult | None = None,
) -> TurnIterationDecision:
    def next_mode(requested_mode: AgentOutputPublicationMode) -> AgentOutputPublicationMode:
        return resolve_next_output_publication_mode(
            current_mode=current_output_publication_mode,
            requested_mode=requested_mode,
        )

    def max_iterations_decision() -> TurnIterationDecision:
        return build_terminal_max_iterations_decision(
            state=state,
            next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )

    def empty_response_decision() -> TurnIterationDecision:
        return build_terminal_empty_response_decision(
            state=state,
            next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )

    if tool_calls:
        return TurnIterationDecision(
            action=TurnIterationAction.PROCEED_TOOLS,
            next_state=copy_turn_iteration_policy_state(
                state,
                tool_call_protocol_retries=0,
                tool_call_protocol_retry_signature="",
            ),
            retry_message=None,
            reached_max_iterations=False,
            terminal_status=None,
            terminal_error_message=None,
            terminal_error_type=None,
            next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )
    if finish_reason == "tool_calls" and is_empty_assistant_output(assistant_text):
        return decide_invalid_tool_call_json_action(
            config=config,
            state=state,
            iteration_index=iteration_index,
            output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )
    if finish_reason == FINISH_REASON_TOOL_SEQUENCE_CONTRACT_VIOLATION:
        if state.tool_sequence_retries < config.max_tool_sequence_retries:
            if is_next_iteration_blocked(
                iteration_index=iteration_index,
                max_iterations=config.max_iterations,
            ):
                return max_iterations_decision()
            return TurnIterationDecision(
                action=TurnIterationAction.RETRY_REQUIRED_VISIBLE_OUTPUT,
                next_state=copy_turn_iteration_policy_state(
                    state,
                    tool_sequence_retries=state.tool_sequence_retries + 1,
                ),
                retry_message=build_tool_sequence_contract_repair_message(),
                reached_max_iterations=False,
                terminal_status=None,
                terminal_error_message=None,
                terminal_error_type=None,
                next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
            )
        return TurnIterationDecision(
            action=TurnIterationAction.TERMINAL_TOOL_SEQUENCE_CONTRACT_VIOLATION,
            next_state=state,
            retry_message=None,
            reached_max_iterations=False,
            terminal_status=AGENT_TURN_STATUS_ERROR,
            terminal_error_message=(
                "Agent turn failed due to an invalid tool message sequence after retries."
            ),
            terminal_error_type="tool_sequence_contract_violation",
            next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )
    if finish_reason == FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION:
        return decide_invalid_tool_call_json_action(
            config=config,
            state=state,
            iteration_index=iteration_index,
            output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )
    if finish_reason == "length":
        if not config.length_finish_reason_retries_enabled:
            if is_empty_assistant_output(assistant_text):
                return empty_response_decision()
            return TurnIterationDecision(
                action=TurnIterationAction.COMPLETE,
                next_state=state,
                retry_message=None,
                reached_max_iterations=False,
                terminal_status=None,
                terminal_error_message=None,
                terminal_error_type=None,
                next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
            )
        if state.length_finish_reason_retries < config.max_length_finish_reason_retries:
            if is_next_iteration_blocked(
                iteration_index=iteration_index,
                max_iterations=config.max_iterations,
            ):
                return max_iterations_decision()
            return TurnIterationDecision(
                action=TurnIterationAction.RETRY_REQUIRED_VISIBLE_OUTPUT,
                next_state=copy_turn_iteration_policy_state(
                    state,
                    length_finish_reason_retries=state.length_finish_reason_retries + 1,
                ),
                retry_message=build_finish_reason_length_continue_message(),
                reached_max_iterations=False,
                terminal_status=None,
                terminal_error_message=None,
                terminal_error_type=None,
                next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
            )
    if should_retry_empty_output_silently(
        config=config,
        state=state,
        assistant_text=assistant_text,
    ):
        if is_next_iteration_blocked(
            iteration_index=iteration_index,
            max_iterations=config.max_iterations,
        ):
            return max_iterations_decision()
        return TurnIterationDecision(
            action=TurnIterationAction.RETRY_SILENT,
            next_state=copy_turn_iteration_policy_state(
                state,
                empty_output_silent_retries=state.empty_output_silent_retries + 1,
            ),
            retry_message=None,
            reached_max_iterations=False,
            terminal_status=None,
            terminal_error_message=None,
            terminal_error_type=None,
            next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )
    if should_retry_empty_output(
        config=config,
        state=state,
        assistant_text=assistant_text,
    ):
        if is_next_iteration_blocked(
            iteration_index=iteration_index,
            max_iterations=config.max_iterations,
        ):
            return max_iterations_decision()
        return TurnIterationDecision(
            action=TurnIterationAction.RETRY_REQUIRED_VISIBLE_OUTPUT,
            next_state=copy_turn_iteration_policy_state(
                state,
                empty_output_retries=state.empty_output_retries + 1,
            ),
            retry_message=build_required_visible_output_message(),
            reached_max_iterations=False,
            terminal_status=None,
            terminal_error_message=None,
            terminal_error_type=None,
            next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )
    if preview_contract_validation is not None and not preview_contract_validation.compliant:
        if state.preview_contract_retries < config.max_preview_contract_retries:
            if is_next_iteration_blocked(
                iteration_index=iteration_index,
                max_iterations=config.max_iterations,
            ):
                return max_iterations_decision()
            return TurnIterationDecision(
                action=TurnIterationAction.RETRY_REQUIRED_VISIBLE_OUTPUT,
                next_state=copy_turn_iteration_policy_state(
                    state,
                    preview_contract_retries=state.preview_contract_retries + 1,
                ),
                retry_message=build_preview_contract_retry_message(
                    preview_contract_validation.retry_detail,
                ),
                reached_max_iterations=False,
                terminal_status=None,
                terminal_error_message=None,
                terminal_error_type=None,
                next_output_publication_mode=(
                    next_mode(AgentOutputPublicationMode.VALIDATE_BEFORE_PUBLISH)
                ),
            )
        return TurnIterationDecision(
            action=TurnIterationAction.TERMINAL_PREVIEW_CONTRACT_VIOLATION,
            next_state=state,
            retry_message=None,
            reached_max_iterations=False,
            terminal_status=AGENT_TURN_STATUS_ERROR,
            terminal_error_message=PREVIEW_CONTRACT_VIOLATION_PUBLIC_MESSAGE,
            terminal_error_type=PREVIEW_CONTRACT_VIOLATION_CODE,
            next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
        )
    if is_empty_assistant_output(assistant_text):
        return empty_response_decision()
    return TurnIterationDecision(
        action=TurnIterationAction.COMPLETE,
        next_state=copy_turn_iteration_policy_state(
            state,
            tool_call_protocol_retries=0,
            tool_call_protocol_retry_signature="",
        ),
        retry_message=None,
        reached_max_iterations=False,
        terminal_status=None,
        terminal_error_message=None,
        terminal_error_type=None,
        next_output_publication_mode=next_mode(AgentOutputPublicationMode.STREAM_LIVE),
    )
