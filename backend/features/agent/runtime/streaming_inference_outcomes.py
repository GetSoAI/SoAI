"""SoAI - Agent streaming inference outcome construction [backend/features/agent/runtime/streaming_inference_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.agent.internal_protocols import AgentStreamingInferenceOutcome

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_agent_streaming_inference_outcome",)


def build_agent_streaming_inference_outcome(
    *,
    payload: JSONDict | None,
    stream_successful: bool,
    done_sent: bool,
    error_message: str | None,
    error_type: str | None,
) -> AgentStreamingInferenceOutcome:
    return AgentStreamingInferenceOutcome(
        payload=payload,
        stream_successful=stream_successful,
        done_sent=done_sent,
        stream_id=None,
        usage=None,
        tool_calls=[],
        visible_text_chars=0,
        thinking_text_chars=0,
        content_index_base=0,
        thinking_index_base=0,
        transcript=None,
        error_message=error_message,
        error_type=error_type,
    )
