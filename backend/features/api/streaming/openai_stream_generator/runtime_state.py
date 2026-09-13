"""SoAI - OpenAI stream generator runtime state [backend/features/api/streaming/openai_stream_generator/runtime_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.openai.streaming_token_budget import StreamingTokenBudgetTracker

__all__ = ("OpenAIStreamRuntimeState",)


@dataclass(slots=True)
class OpenAIStreamRuntimeState:
    is_done_sent: bool
    is_stream_successful: bool
    abort_stream: bool
    cancel_scheduled: bool
    done_marker_observed: bool
    chunk_accumulator: OpenAISSEFrameAccumulator
    stream_transcript: OpenAIStreamTranscript | None
    stream_id: str | None
    stream_object: str | None
    quota_completion_token_budget: StreamingTokenBudgetTracker | None
    collect_tool_calls: bool
    tool_call_ids_by_index: dict[int, str] = field(default_factory=dict[int, str])
    tool_call_ids_by_ordinal: dict[int, str] = field(default_factory=dict[int, str])
