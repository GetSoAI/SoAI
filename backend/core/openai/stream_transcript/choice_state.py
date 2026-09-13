"""SoAI - Independent OpenAI completion choice state [backend/core/openai/stream_transcript/choice_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ModelOutputContractError
from core.openai.completion_token_progress import CompletionTokenSnapshotCursor
from core.openai.stream_transcript.payload_segments import (
    extract_reasoning_text_from_source,
    iter_choice_tool_call_sources,
    iter_text_segments_from_payload,
)
from core.openai.stream_transcript.text_classifier import OpenAIStreamTextClassifier
from core.openai.stream_transcript.tool_call_state import OpenAIStreamToolCallState
from core.openai.tool_call_stream_matching import (
    source_has_content,
    source_has_reasoning,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("OpenAICompletionChoice",)


class OpenAICompletionChoice:
    def __init__(
        self,
        *,
        result_format: Literal["chat", "completions"],
        clock_ms: Callable[[], int],
        collect_tool_calls: bool,
    ) -> None:
        self._result_format = result_format
        self._collect_tool_calls = collect_tool_calls
        self.logprobs: JSONDict | None = None
        self.finish_reason: str | None = None
        self.text = OpenAIStreamTextClassifier(clock_ms=clock_ms)
        self.tool_calls = OpenAIStreamToolCallState(
            flush_text_boundary=self.text.flush_for_tool_call_boundary,
            get_content_index_before=self.text.get_visible_content_char_count,
            get_thinking_index_before=self.text.get_thinking_char_count,
            get_thinking_duration_before_ms=self.text.get_thinking_tail_duration_ms,
        )
        self.tool_token_cursor = CompletionTokenSnapshotCursor()

    def finalize(self) -> None:
        self.text.finalize()
        self.tool_calls.finalize_implicit_chronology(
            content_index_before=self.text.get_visible_content_char_count(),
            thinking_index_before=self.text.get_thinking_char_count(),
        )

    def drain_completion_token_fragments(self) -> tuple[str, ...]:
        text_fragments = self.text.drain_completion_token_fragments()
        tool_fragments = self.tool_token_cursor.take(
            visible_text="",
            thinking_text="",
            tool_calls=self.tool_calls.get_tool_calls(),
        )
        return text_fragments + tool_fragments

    def consume(self, choice: JSONDict) -> None:
        finish_reason_value = choice.get("finish_reason")
        if isinstance(finish_reason_value, str) and finish_reason_value:
            normalized_finish_reason = self.normalize_finish_reason(finish_reason_value)
            if normalized_finish_reason:
                self.finish_reason = normalized_finish_reason
        delta_value = choice.get("delta")
        delta = delta_value if isinstance(delta_value, dict) else None
        message_value = choice.get("message")
        message = message_value if isinstance(message_value, dict) else None
        self._consume_logprobs(choice.get("logprobs"), snapshot=message is not None)
        reasoning_source: JSONDict | None = None
        if isinstance(delta, dict) and source_has_reasoning(delta):
            reasoning_source = delta
        elif isinstance(message, dict) and source_has_reasoning(message):
            reasoning_source = message
        if reasoning_source is not None:
            reasoning_text = extract_reasoning_text_from_source(reasoning_source)
            if reasoning_text:
                self.text.consume_reasoning_text(reasoning_text)
        if isinstance(delta, dict) and source_has_content(delta):
            for segment in iter_text_segments_from_payload(delta.get("content")):
                if segment.channel == "thinking":
                    self.text.consume_reasoning_text(segment.text)
                else:
                    self.text.consume_content_text(segment.text)
        else:
            text_value = choice.get("text")
            if isinstance(text_value, str) and text_value:
                self.text.consume_content_text(text_value)
        if isinstance(message, dict):
            self._consume_choice_message_snapshot(message)
        if self._collect_tool_calls:
            for tool_call_source in iter_choice_tool_call_sources(choice):
                self.tool_calls.consume_tool_calls_payload(tool_call_source)

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
        self.text.flush_for_tool_call_boundary()
        current = self.text.get_visible_text()
        if snapshot_text.startswith(current):
            suffix = snapshot_text[len(current) :]
            if suffix:
                self.text.consume_content_text(suffix)
            return
        if current.startswith(snapshot_text):
            return

    def consume_unindexed_payload(self, payload: JSONDict) -> None:
        text_source: JSONDict = {}
        for key in ("reasoning_content", "reasoning", "thinking"):
            if key in payload:
                text_source[key] = payload.get(key)
                break
        if "content" in payload:
            text_source["content"] = payload.get("content")
        if text_source:
            self.text.consume_text_source(text_source)
        if self._collect_tool_calls and "tool_calls" in payload:
            self.tool_calls.consume_tool_calls_payload(payload)

    def normalize_finish_reason(self, finish_reason: str) -> str:
        normalized = finish_reason.strip()
        if not self._collect_tool_calls and normalized.lower() == "tool_calls":
            return "stop"
        return normalized

    def _consume_logprobs(self, value: JSONValue, *, snapshot: bool) -> None:
        if value is None:
            return
        if not isinstance(value, dict):
            raise ModelOutputContractError("The model returned invalid token probabilities.")
        if self.logprobs is None:
            self.logprobs = {}
        fields = (
            ("content", "refusal")
            if self._result_format == "chat"
            else ("tokens", "token_logprobs", "top_logprobs", "text_offset")
        )
        for field in fields:
            if field not in value:
                continue
            incoming = value[field]
            previous = self.logprobs.get(field)
            if incoming is None:
                if field not in self.logprobs:
                    self.logprobs[field] = None
                continue
            if not isinstance(incoming, list):
                raise ModelOutputContractError("The model returned invalid token probabilities.")
            if not isinstance(previous, list):
                self.logprobs[field] = deepcopy(incoming)
            elif not snapshot:
                previous.extend(deepcopy(incoming))
            elif incoming[: len(previous)] == previous:
                self.logprobs[field] = deepcopy(incoming)
            elif previous[: len(incoming)] != incoming:
                raise ModelOutputContractError(
                    "The model returned inconsistent token probabilities."
                )
