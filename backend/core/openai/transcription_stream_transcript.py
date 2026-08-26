"""SoAI - OpenAI transcription SSE transcript [backend/core/openai/transcription_stream_transcript.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Never

from core.errors.exceptions import ModelOutputContractError
from core.openai.payload_validation import decode_streaming_text_chunk
from core.openai.sse_block_decoder import decode_openai_sse_block

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict, JSONValue

__all__ = ("OpenAITranscriptionStreamTranscript",)

_TRANSCRIPTION_EVENT_TYPES: frozenset[str] = frozenset(
    {"transcript.text.delta", "transcript.text.done"},
)


class OpenAITranscriptionStreamTranscript:
    def __init__(self) -> None:
        self._deltas: list[str] = []
        self._final_text: str | None = None
        self._usage: JSONDict | None = None
        self._terminal_observed = False
        self._finalized = False
        self._token_fragment_cursor = 0
        self._final_text_drained = False

    @property
    def terminal_observed(self) -> bool:
        return self._terminal_observed

    def feed(self, frame: StreamChunk) -> None:
        if self._finalized:
            self._raise_contract_error("Provider emitted transcription data after finalization.")
        frame_text = decode_streaming_text_chunk(frame)
        if frame_text is None:
            self._raise_contract_error("Provider returned invalid transcription stream bytes.")
        decoded = decode_openai_sse_block(frame_text)
        if not decoded.is_terminated or not decoded.is_well_formed:
            self._raise_contract_error("Provider returned a malformed transcription SSE frame.")
        for data_event in decoded.data_events:
            if data_event.is_done:
                self._raise_contract_error(
                    "Provider returned an unsupported [DONE] transcription marker.",
                )
            payload = data_event.payload
            if payload is None:
                self._raise_contract_error("Provider returned an empty transcription event.")
            self._consume_payload(payload)

    def finalize(self) -> None:
        if self._finalized:
            return
        if not self._terminal_observed:
            self._raise_contract_error(
                "Provider transcription stream ended before transcript.text.done.",
            )
        self._finalized = True

    def build_result_payload(self) -> JSONDict:
        if not self._terminal_observed or self._final_text is None:
            self._raise_contract_error("Transcription stream has no completed result.")
        result: JSONDict = {"text": self._final_text}
        if self._usage is not None:
            result["usage"] = dict(self._usage)
        return result

    def get_reported_usage(self) -> JSONDict | None:
        return dict(self._usage) if self._usage is not None else None

    def get_visible_text(self) -> str:
        if self._final_text is not None:
            return self._final_text
        return "".join(self._deltas)

    def get_thinking_text(self) -> str:
        return ""

    def get_tool_calls(self) -> list[JSONDict]:
        return []

    def drain_completion_token_fragments(self) -> tuple[str, ...]:
        fragments = tuple(self._deltas[self._token_fragment_cursor :])
        self._token_fragment_cursor = len(self._deltas)
        if self._final_text is not None and not self._deltas and not self._final_text_drained:
            self._final_text_drained = True
            return (self._final_text,)
        return fragments

    def _consume_payload(self, payload: JSONDict) -> None:
        event_type_value = payload.get("type")
        if (
            not isinstance(event_type_value, str)
            or event_type_value not in _TRANSCRIPTION_EVENT_TYPES
        ):
            self._raise_contract_error("Provider returned an unsupported transcription event.")
        if self._terminal_observed:
            self._raise_contract_error(
                "Provider emitted transcription data after transcript.text.done.",
            )
        if event_type_value == "transcript.text.delta":
            self._consume_delta(payload)
            return
        self._consume_done(payload)

    def _consume_delta(self, payload: JSONDict) -> None:
        delta_value = payload.get("delta")
        if not isinstance(delta_value, str):
            self._raise_contract_error("Transcription delta event is missing a string delta.")
        self._validate_optional_logprobs(payload.get("logprobs"))
        self._deltas.append(delta_value)

    def _consume_done(self, payload: JSONDict) -> None:
        text_value = payload.get("text")
        if not isinstance(text_value, str):
            self._raise_contract_error("Transcription done event is missing string text.")
        self._validate_optional_logprobs(payload.get("logprobs"))
        usage_value = payload.get("usage")
        if usage_value is not None and not isinstance(usage_value, dict):
            self._raise_contract_error("Transcription done usage must be an object.")
        self._final_text = text_value
        self._usage = dict(usage_value) if isinstance(usage_value, dict) else None
        self._terminal_observed = True

    def _validate_optional_logprobs(self, value: JSONValue) -> None:
        if value is not None and not isinstance(value, list):
            self._raise_contract_error("Transcription event logprobs must be an array.")

    def _raise_contract_error(self, message: str) -> Never:
        raise ModelOutputContractError(
            message,
            operation="core.openai.transcription_stream_transcript",
            details={"failure_type": "invalid_transcription_stream"},
        )
