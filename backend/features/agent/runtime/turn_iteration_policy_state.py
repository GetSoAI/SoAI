"""SoAI - Agent turn iteration policy state transitions [backend/features/agent/runtime/turn_iteration_policy_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.agent.runtime.turn_iteration_policy_types import TurnIterationPolicyState

__all__ = ("copy_turn_iteration_policy_state",)


def copy_turn_iteration_policy_state(
    state: TurnIterationPolicyState,
    *,
    empty_output_retries: int | None = None,
    empty_output_silent_retries: int | None = None,
    length_finish_reason_retries: int | None = None,
    tool_sequence_retries: int | None = None,
    invalid_tool_call_json_retries: int | None = None,
    tool_call_protocol_retries: int | None = None,
    tool_call_protocol_retry_signature: str = "",
    preview_contract_retries: int | None = None,
) -> TurnIterationPolicyState:
    resolved_tool_call_protocol_retry_signature = (
        tool_call_protocol_retry_signature
        if tool_call_protocol_retries is not None or tool_call_protocol_retry_signature
        else state.tool_call_protocol_retry_signature
    )
    return TurnIterationPolicyState(
        empty_output_retries=(
            state.empty_output_retries if empty_output_retries is None else empty_output_retries
        ),
        empty_output_silent_retries=(
            state.empty_output_silent_retries
            if empty_output_silent_retries is None
            else empty_output_silent_retries
        ),
        length_finish_reason_retries=(
            state.length_finish_reason_retries
            if length_finish_reason_retries is None
            else length_finish_reason_retries
        ),
        tool_sequence_retries=(
            state.tool_sequence_retries if tool_sequence_retries is None else tool_sequence_retries
        ),
        invalid_tool_call_json_retries=(
            state.invalid_tool_call_json_retries
            if invalid_tool_call_json_retries is None
            else invalid_tool_call_json_retries
        ),
        tool_call_protocol_retries=(
            state.tool_call_protocol_retries
            if tool_call_protocol_retries is None
            else tool_call_protocol_retries
        ),
        tool_call_protocol_retry_signature=resolved_tool_call_protocol_retry_signature,
        preview_contract_retries=(
            state.preview_contract_retries
            if preview_contract_retries is None
            else preview_contract_retries
        ),
    )
