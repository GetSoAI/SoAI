"""SoAI - Non-streaming OpenAI SSE reconstruction [backend/features/api/streaming/non_streaming_sse_reconstructor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal, override

from core.logging.trace import get_logger
from core.openai.openai_error_objects import parse_openai_sse_error_frame
from core.openai.openai_sse_error_escalation import raise_openai_streaming_error
from core.openai.request_fields import resolve_optional_model_name
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_validation import (
    OPENAI_SSE_PENDING_BUFFER_LIMIT_BYTES,
    validate_openai_sse_frame,
)
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NonStreamingSSEMalformedFrameError",
    "NonStreamingSSEReconstructor",
)

LOGGER_NAME = "SoAI.features.api.non_streaming_sse_reconstructor"
OPERATION_CONSUME_SSE = "api.streaming.non_streaming_sse_reconstructor.consume"


class NonStreamingSSEMalformedFrameError(ValueError):
    def __init__(self, *, frame_preview: str) -> None:
        super().__init__("Malformed OpenAI SSE frame.")
        self.frame_preview = frame_preview

    @override
    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""

    def __getnewargs_ex__(self) -> tuple[tuple[()], dict[str, str]]:
        return ((), {"frame_preview": self.frame_preview})


class NonStreamingSSEReconstructor:
    __slots__ = (
        "_accumulator",
        "_allow_image_events",
        "_converter_format",
        "_transcript",
    )

    def __init__(
        self,
        *,
        allow_image_events: bool,
        converter_format: Literal["chat", "completions"],
        buffer_limit_bytes: int = OPENAI_SSE_PENDING_BUFFER_LIMIT_BYTES,
    ) -> None:
        self._accumulator = OpenAISSEFrameAccumulator(
            buffer_limit_bytes=buffer_limit_bytes,
        )
        self._converter_format: Literal["chat", "completions"] = converter_format
        self._allow_image_events = allow_image_events
        self._transcript: OpenAIStreamTranscript | None = None

    @property
    def transcript(self) -> OpenAIStreamTranscript | None:
        return self._transcript

    def consume_chunk(
        self,
        *,
        context: RequestContext,
        request_json: Mapping[str, JSONValue],
        chunk: StreamChunk,
        buffering_log_label: str,
    ) -> None:
        for frame in self._accumulator.feed(chunk):
            if not validate_openai_sse_frame(
                frame,
                allow_image_events=self._allow_image_events,
            ):
                frame_preview = frame[:200] if frame else "(empty)"
                raise NonStreamingSSEMalformedFrameError(frame_preview=frame_preview)
            parsed_error = parse_openai_sse_error_frame(frame)
            if parsed_error is not None:
                raise_openai_streaming_error(parsed_error, operation=OPERATION_CONSUME_SSE)
            if self._transcript is None:
                self._transcript = OpenAIStreamTranscript(
                    model_hint=resolve_optional_model_name(request_json),
                    result_format=self._converter_format,
                )
                self._log_buffering(context, buffering_log_label)
            self._transcript.feed(frame)

    def finalize(self) -> JSONDict | None:
        self._accumulator.finalize()
        if self._transcript is None:
            return None
        self._transcript.finalize()
        return self._transcript.build_result_payload()

    def _log_buffering(self, context: RequestContext, buffering_log_label: str) -> None:
        logger = get_logger(LOGGER_NAME)
        if buffering_log_label:
            logger.warning(
                "[%s] Backend sent streaming events for non-streaming request %s. Buffering frames.",
                context.trace_id,
                buffering_log_label,
            )
            return
        logger.warning(
            "[%s] Backend sent streaming events for non-streaming request. Buffering frames.",
            context.trace_id,
        )
