"""SoAI - Agent model output contract recovery [backend/features/agent/runtime/model_output_contract_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.model_output_contract_errors import (
    is_invalid_tool_call_json_contract_error,
)
from core.openai.stream_transcript.payload_segments import (
    build_choice_text_source,
    extract_reasoning_text_from_source,
)
from core.openai.text_tool_call_extraction import contains_text_tool_call_markup
from core.types.json import JSONDict
from features.agent.internal_protocols import AgentStreamingInferenceOutcome
from features.agent.runtime.turn_iteration_policy_types import (
    FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION,
)

__all__ = (
    "build_invalid_tool_call_json_retry_payload",
    "is_invalid_tool_call_json_outcome",
    "payload_hidden_reasoning_contains_tool_call_markup",
    "recover_streaming_invalid_tool_call_json_outcome",
)


def payload_hidden_reasoning_contains_tool_call_markup(payload: JSONDict) -> bool:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        source = build_choice_text_source(choice)
        reasoning_text = extract_reasoning_text_from_source(source)
        if contains_text_tool_call_markup(reasoning_text):
            return True
    return False


def is_invalid_tool_call_json_outcome(
    *,
    error_message: str | None,
    error_type: str | None,
) -> bool:
    return is_invalid_tool_call_json_contract_error(
        message=error_message,
        error_type=error_type,
    )


def build_invalid_tool_call_json_retry_payload() -> JSONDict:
    return {
        "id": "soai_retry_invalid_tool_call_json",
        "choices": [
            {
                "finish_reason": FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION,
                "message": {"role": "assistant", "content": ""},
            },
        ],
    }


def recover_streaming_invalid_tool_call_json_outcome(
    *,
    outcome: AgentStreamingInferenceOutcome,
) -> AgentStreamingInferenceOutcome:
    if not is_invalid_tool_call_json_outcome(
        error_message=outcome.error_message,
        error_type=outcome.error_type,
    ):
        return outcome
    payload = build_invalid_tool_call_json_retry_payload()
    return AgentStreamingInferenceOutcome(
        payload=payload,
        stream_successful=True,
        done_sent=outcome.done_sent,
        stream_id=outcome.stream_id,
        usage=outcome.usage,
        tool_calls=[],
        visible_text_chars=0,
        thinking_text_chars=0,
        content_index_base=outcome.content_index_base,
        thinking_index_base=outcome.thinking_index_base,
        transcript=outcome.transcript,
        error_message=None,
        error_type=None,
    )
