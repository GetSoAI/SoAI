"""SoAI - OpenAI stream frame processing primitives [backend/core/openai/stream_frame_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.openai.sse_events import chunk_contains_done_marker, strip_done_marker_lines
from core.openai.streaming_text_deltas import (
    extract_openai_streaming_event_id,
    extract_openai_streaming_event_object,
)

__all__ = (
    "OpenAIStreamFrame",
    "process_openai_stream_frame",
)


@dataclass(frozen=True, slots=True)
class OpenAIStreamFrame:
    text: str
    filtered_text: str
    done_marker_observed: bool
    stream_id: str | None
    stream_object: str | None


def process_openai_stream_frame(frame_text: str) -> OpenAIStreamFrame:
    stream_id = extract_openai_streaming_event_id(frame_text)
    stream_object = extract_openai_streaming_event_object(frame_text)
    done_marker_observed = chunk_contains_done_marker(frame_text)
    filtered_text = strip_done_marker_lines(frame_text) if done_marker_observed else frame_text
    return OpenAIStreamFrame(
        text=frame_text,
        filtered_text=filtered_text,
        done_marker_observed=done_marker_observed,
        stream_id=stream_id if stream_id else None,
        stream_object=stream_object if stream_object else None,
    )
