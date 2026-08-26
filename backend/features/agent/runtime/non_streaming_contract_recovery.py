"""SoAI - Non-streaming model output contract recovery [backend/features/agent/runtime/non_streaming_contract_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SoAIError
from features.agent.runtime.model_output_contract_recovery import (
    build_invalid_tool_call_json_retry_payload,
    is_invalid_tool_call_json_outcome,
)
from features.agent.runtime.non_streaming_inference_results import (
    build_successful_non_streaming_inference_result,
)
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult

__all__ = ("build_non_streaming_contract_recovery_result",)


def build_non_streaming_contract_recovery_result(
    error: SoAIError,
) -> TurnLoopInferenceResult | None:
    if not is_invalid_tool_call_json_outcome(
        error_message=error.message,
        error_type=str(error.code),
    ):
        return None
    payload = build_invalid_tool_call_json_retry_payload()
    return build_successful_non_streaming_inference_result(
        payload=payload,
        assistant_text="",
        include_usage=False,
    )
