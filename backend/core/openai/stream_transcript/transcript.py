"""SoAI - Canonical OpenAI stream transcript [backend/core/openai/stream_transcript/transcript.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from core.openai.completion_token_progress import CompletionTokenSnapshotCursor
from core.openai.openai_error_objects import parse_openai_sse_error_frame
from core.openai.openai_sse_error_escalation import raise_openai_streaming_error
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.openai.stream_transcript.payload_segments import (
    extract_reasoning_text_from_source,
    iter_choice_tool_call_sources,
    iter_text_segments_from_payload,
)
from core.openai.stream_transcript.result_payloads import (
    OpenAIStreamResultPayloadInputs,
    build_openai_stream_result_payload,
)
from core.openai.stream_transcript.text_classifier import OpenAIStreamTextClassifier
from core.openai.stream_transcript.tool_call_state import OpenAIStreamToolCallState
from core.openai.tool_call_stream_matching import (
    source_has_content,
    source_has_reasoning,
)
from core.openai.usage.serialization import extract_public_usage_payload
from core.timing.monotonic import monotonic_ms
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict, JSONValue

__all__ = ("OpenAIStreamTranscript",)

OPERATION_CONSUME_FRAME = "core.openai.stream_transcript.consume_frame"


class OpenAIStreamTranscript:
    def __init__(
        self,
        model_hint: str | None = None,
        *,
        result_format: Literal["chat", "completions"] = "chat",
        clock_ms: Callable[[], int] = monotonic_ms,
        collect_tool_calls: bool = True,
    ) -> None:
        self._frame_accumulator = OpenAISSEFrameAccumulator()
        self._result_format: Literal["chat", "completions"] = result_format
        self._model: str | None = model_hint
        self._usage: JSONDict | None = None
        self._finish_reason: str | None = None
        self._collect_tool_calls: bool = collect_tool_calls
        self._result_created_at: int | None = None
        self._result_id: str | None = None
        self._finalized = False
        self._text = OpenAIStreamTextClassifier(
            clock_ms=clock_ms,
        )
        self._tool_calls = OpenAIStreamToolCallState(
            flush_text_boundary=self._text.flush_for_tool_call_boundary,
            get_content_index_before=self._text.get_visible_content_char_count,
            get_thinking_index_before=self._text.get_thinking_char_count,
            get_thinking_duration_before_ms=self._text.get_thinking_tail_duration_ms,
        )
        self._tool_token_cursor = CompletionTokenSnapshotCursor()

    def _extract_visible_text(self, content: JSONValue | None) -> str:
        if content is None:
            return ""
        parts: list[str] = []
        for segment in iter_text_segments_from_payload(content):
            if segment.channel != "thinking" and segment.text:
                parts.append(segment.text)
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        return "".join(parts)

    def _consume_choice_message_snapshot(self, message: JSONDict) -> None:
        if not isinstance(message, dict) or not source_has_content(message):
            return
        snapshot_text = self._extract_visible_text(message.get("content"))
        if not snapshot_text:
            return
        self._text.flush_for_tool_call_boundary()
        current = self._text.get_visible_text()
        if snapshot_text.startswith(current):
            suffix = snapshot_text[len(current) :]
            if suffix:
                self._text.consume_content_text(suffix)
            return
        if current.startswith(snapshot_text):
            return

    def feed(self, chunk: StreamChunk) -> None:
        for frame in self._frame_accumulator.feed(chunk):
            self._consume_frame(frame)

    def finalize(self) -> JSONDict:
        if self._finalized:
            return self.build_result_payload()
        self._frame_accumulator.finalize()
        self._text.finalize()
        self._tool_calls.finalize_implicit_chronology(
            content_index_before=self._text.get_visible_content_char_count(),
            thinking_index_before=self._text.get_thinking_char_count(),
        )
        self._finalized = True
        return self.build_result_payload()

    def _consume_frame(self, frame: str) -> None:
        parsed_error = parse_openai_sse_error_frame(frame)
        if parsed_error is not None:
            raise_openai_streaming_error(parsed_error, operation=OPERATION_CONSUME_FRAME)
        for payload in parse_openai_sse_frame_payloads(frame):
            self._consume_payload(payload)

    def _consume_payload(self, payload: JSONValue) -> None:
        if not isinstance(payload, dict):
            return
        payload_id = payload.get("id")
        if isinstance(payload_id, str) and payload_id:
            self._result_id = payload_id
        created_value = payload.get("created")
        if is_strict_int(created_value):
            self._result_created_at = int(created_value)
        model_value = payload.get("model")
        if isinstance(model_value, str) and model_value:
            self._model = model_value
        usage_value = payload.get("usage")
        usage_payload = extract_public_usage_payload(usage_value)
        if usage_payload is not None:
            self._usage = usage_payload
        choices_value = payload.get("choices")
        if not isinstance(choices_value, list):
            self._consume_text_and_tool_payload(payload)
            return
        for choice in choices_value:
            if not isinstance(choice, dict):
                continue
            finish_reason_value = choice.get("finish_reason")
            if isinstance(finish_reason_value, str) and finish_reason_value:
                normalized_finish_reason = self._normalize_finish_reason(finish_reason_value)
                if normalized_finish_reason:
                    self._finish_reason = normalized_finish_reason
            delta_value = choice.get("delta")
            delta = delta_value if isinstance(delta_value, dict) else None
            message_value = choice.get("message")
            message = message_value if isinstance(message_value, dict) else None
            reasoning_source: JSONDict | None = None
            if isinstance(delta, dict) and source_has_reasoning(delta):
                reasoning_source = delta
            elif isinstance(message, dict) and source_has_reasoning(message):
                reasoning_source = message
            if reasoning_source is not None:
                reasoning_text = extract_reasoning_text_from_source(reasoning_source)
                if reasoning_text:
                    self._text.consume_reasoning_text(reasoning_text)
            if isinstance(delta, dict) and source_has_content(delta):
                for segment in iter_text_segments_from_payload(delta.get("content")):
                    if segment.channel == "thinking":
                        self._text.consume_reasoning_text(segment.text)
                    else:
                        self._text.consume_content_text(segment.text)
            else:
                text_value = choice.get("text")
                if isinstance(text_value, str) and text_value:
                    self._text.consume_content_text(text_value)
            if isinstance(message, dict):
                self._consume_choice_message_snapshot(message)
            if self._collect_tool_calls:
                for tool_call_source in iter_choice_tool_call_sources(choice):
                    self._tool_calls.consume_tool_calls_payload(tool_call_source)

    def _consume_text_and_tool_payload(self, payload: JSONDict) -> None:
        text_source: JSONDict = {}
        for key in ("reasoning_content", "reasoning", "thinking"):
            if key in payload:
                text_source[key] = payload.get(key)
                break
        if "content" in payload:
            text_source["content"] = payload.get("content")
        if text_source:
            self._text.consume_text_source(text_source)
        if self._collect_tool_calls and "tool_calls" in payload:
            self._tool_calls.consume_tool_calls_payload(payload)

    def drain_visible_text_deltas(self) -> tuple[str, ...]:
        return self._text.drain_visible_text_deltas()

    def drain_thinking_text_deltas(self) -> tuple[str, ...]:
        return self._text.drain_thinking_text_deltas()

    def get_visible_text(self) -> str:
        return self._text.get_visible_text()

    def get_thinking_text(self) -> str:
        return self._text.get_thinking_text()

    def get_visible_content_char_count(self) -> int:
        return self._text.get_visible_content_char_count()

    def get_thinking_char_count(self) -> int:
        return self._text.get_thinking_char_count()

    def get_thinking_tail_duration_ms(self) -> int:
        return self._text.get_thinking_tail_duration_ms()

    def get_thinking_tail_content_index_before(self) -> int:
        return self._text.get_thinking_tail_content_index_before()

    def drain_thinking_close_events(self) -> int:
        return self._text.drain_thinking_close_events()

    def collects_tool_calls(self) -> bool:
        return self._collect_tool_calls

    def get_tool_calls(self) -> list[JSONDict]:
        return self._tool_calls.get_tool_calls()

    def drain_completion_token_fragments(self) -> tuple[str, ...]:
        text_fragments = self._text.drain_completion_token_fragments()
        tool_fragments = self._tool_token_cursor.take(
            visible_text="",
            thinking_text="",
            tool_calls=self._tool_calls.get_tool_calls(),
        )
        return text_fragments + tool_fragments

    def get_tool_call_contract_violation_summary(self) -> JSONDict | None:
        return self._tool_calls.get_tool_call_contract_violation_summary()

    def get_reported_usage(self) -> JSONDict | None:
        if self._usage is None:
            return None
        return dict(self._usage)

    def drain_new_tool_calls(self) -> list[JSONDict]:
        return self._tool_calls.drain_new_tool_calls()

    def set_finish_reason(self, finish_reason: str) -> None:
        normalized = self._normalize_finish_reason(finish_reason)
        if not normalized:
            return
        self._finish_reason = normalized

    def _normalize_finish_reason(self, finish_reason: str) -> str:
        normalized = finish_reason.strip()
        if not self._collect_tool_calls and normalized.lower() == "tool_calls":
            return "stop"
        return normalized

    def build_result_payload(self, usage: JSONDict | None = None) -> JSONDict:
        result = build_openai_stream_result_payload(
            OpenAIStreamResultPayloadInputs(
                result_format=self._result_format,
                result_id=self._result_id,
                result_created_at=self._result_created_at,
                model=self._model,
                finish_reason=self._finish_reason,
                content=self._text.get_visible_text(),
                reasoning_content=self._text.get_thinking_text(),
                tool_calls=self._tool_calls.get_tool_calls(),
                stored_usage=self._usage,
                override_usage=usage,
            ),
        )
        self._result_id = result.result_id
        self._result_created_at = result.result_created_at
        return result.payload
