"""SoAI - Non-streaming turn-loop inference result construction [backend/features/agent/runtime/non_streaming_inference_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.agent.runtime.openai_payload import extract_finish_reason, extract_usage
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_successful_non_streaming_inference_result",)


def build_successful_non_streaming_inference_result(
    *,
    payload: JSONDict,
    assistant_text: str,
    include_usage: bool,
) -> TurnLoopInferenceResult:
    return TurnLoopInferenceResult(
        payload=payload,
        assistant_text=assistant_text,
        finish_reason=extract_finish_reason(payload),
        usage=extract_usage(payload) if include_usage else None,
        stream_id=None,
        successful=True,
        error_message=None,
        error_type=None,
        assistant_output_published=True,
        tool_calls=[],
        visible_text_chars=0,
        thinking_text_chars=0,
        error_details=None,
    )
