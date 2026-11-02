"""SoAI - OpenAI stream generator provider error frame handling [backend/features/api/streaming/openai_stream_generator/provider_error_frames.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.openai_error_objects import extract_openai_sse_error_from_payloads
from core.openai.openai_sse_error_escalation import OpenAIStreamError, raise_openai_streaming_error
from core.openai.sse_frame_payloads import require_openai_sse_frame_payloads
from features.api.streaming.openai_stream_generator.stream_abort import (
    OpenAIStreamAbortRequested,
)

if TYPE_CHECKING:
    from core.openai.sse_block_decoder import DecodedSSEBlock

__all__ = ("raise_provider_sse_error_if_present",)


def raise_provider_sse_error_if_present(decoded_frame: DecodedSSEBlock) -> None:
    parsed_error = extract_openai_sse_error_from_payloads(
        require_openai_sse_frame_payloads(decoded_frame)
    )
    del decoded_frame
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
