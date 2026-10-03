"""SoAI - OpenAI stream generator provider error frame handling [backend/features/api/streaming/openai_stream_generator/provider_error_frames.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.openai_error_objects import parse_openai_sse_error_frame
from core.openai.openai_sse_error_escalation import OpenAIStreamError, raise_openai_streaming_error
from features.api.streaming.openai_stream_generator.stream_abort import (
    OpenAIStreamAbortRequested,
)

__all__ = ("raise_provider_sse_error_if_present",)


def raise_provider_sse_error_if_present(frame_text: str) -> None:
    parsed_error = parse_openai_sse_error_frame(frame_text)
    if parsed_error is None:
        return
    try:
        raise_openai_streaming_error(
            parsed_error,
            operation="streaming.provider_error_frame",
        )
    except OpenAIStreamError as exception:
        raise OpenAIStreamAbortRequested(
            exception.message,
            str(exception.code),
        ) from exception
