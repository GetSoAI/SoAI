"""SoAI - Canonical OpenAI stream transcript [backend/core/openai/stream_transcript/transcript.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ModelOutputContractError
from core.openai.openai_error_objects import parse_openai_sse_error_frame
from core.openai.openai_sse_error_escalation import raise_openai_streaming_error
from core.openai.response_metrics import parse_response_metrics
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.openai.stream_transcript.choice_state import OpenAICompletionChoice
from core.openai.stream_transcript.result_payloads import (
    OpenAIStreamChoicePayload,
    OpenAIStreamResultPayloadInputs,
    build_openai_stream_result_payload,
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
        self._metrics: JSONDict | None = None
        self._collect_tool_calls: bool = collect_tool_calls
        self._result_created_at: int | None = None
        self._result_id: str | None = None
        self._finalized = False
        self._clock_ms = clock_ms
        self._choices: dict[int, OpenAICompletionChoice] = {}
        self._observed_choices: set[int] = set()
        self._primary = self._choice(0)

    def _choice(self, index: int) -> OpenAICompletionChoice:
        choice = self._choices.get(index)
        if choice is None:
            choice = OpenAICompletionChoice(
                result_format=self._result_format,
                clock_ms=self._clock_ms,
                collect_tool_calls=self._collect_tool_calls,
            )
            self._choices[index] = choice
        return choice

    def feed(self, chunk: StreamChunk) -> None:
        for frame in self._frame_accumulator.feed(chunk):
            self._consume_frame(frame)

    def finalize(self) -> JSONDict:
        if self._finalized:
            return self.build_result_payload()
        self._frame_accumulator.finalize()
        for choice in self._choices.values():
            choice.finalize()
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
        metrics = parse_response_metrics(payload.get("metrics"))
        if metrics is not None:
            self._metrics = metrics
        choices_value = payload.get("choices")
        if not isinstance(choices_value, list):
            self._observed_choices.add(0)
            self._primary.consume_unindexed_payload(payload)
            return
        frame_indices: set[int] = set()
        for choice in choices_value:
            if not isinstance(choice, dict):
                raise ModelOutputContractError("The model returned an invalid completion choice.")
            index = choice.get("index", 0)
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or index < 0
                or index in frame_indices
            ):
                raise ModelOutputContractError(
                    "The model returned an invalid completion choice index."
                )
            frame_indices.add(index)
            self._observed_choices.add(index)
            self._choice(index).consume(choice)

    def drain_visible_text_deltas(self) -> tuple[str, ...]:
        return self._primary.text.drain_visible_text_deltas()

    def drain_thinking_text_deltas(self) -> tuple[str, ...]:
        return self._primary.text.drain_thinking_text_deltas()

    def get_visible_text(self) -> str:
        return self._primary.text.get_visible_text()

    def get_thinking_text(self) -> str:
        return self._primary.text.get_thinking_text()

    def get_visible_content_char_count(self) -> int:
        return self._primary.text.get_visible_content_char_count()

    def get_thinking_char_count(self) -> int:
        return self._primary.text.get_thinking_char_count()

    def get_thinking_tail_duration_ms(self) -> int:
        return self._primary.text.get_thinking_tail_duration_ms()

    def get_thinking_tail_content_index_before(self) -> int:
        return self._primary.text.get_thinking_tail_content_index_before()

    def drain_thinking_close_events(self) -> int:
        return self._primary.text.drain_thinking_close_events()

    def collects_tool_calls(self) -> bool:
        return self._collect_tool_calls

    def get_tool_calls(self) -> list[JSONDict]:
        return self._primary.tool_calls.get_tool_calls()

    def drain_completion_token_fragments(self) -> tuple[str, ...]:
        return tuple(
            fragment
            for index in sorted(self._choices)
            for fragment in self._choices[index].drain_completion_token_fragments()
        )

    def get_tool_call_contract_violation_summary(self) -> JSONDict | None:
        for index in sorted(self._choices):
            summary = self._choices[index].tool_calls.get_tool_call_contract_violation_summary()
            if summary is not None:
                return summary if index == 0 else {**summary, "choice_index": index}
        return None

    def get_reported_usage(self) -> JSONDict | None:
        if self._usage is None:
            return None
        return dict(self._usage)

    def drain_new_tool_calls(self) -> list[JSONDict]:
        return self._primary.tool_calls.drain_new_tool_calls()

    def set_finish_reason(self, finish_reason: str) -> None:
        normalized = self._primary.normalize_finish_reason(finish_reason)
        if not normalized:
            return
        self._primary.finish_reason = normalized

    def build_result_payload(self, usage: JSONDict | None = None) -> JSONDict:
        choices: list[OpenAIStreamChoicePayload] = []
        for index in sorted(self._observed_choices or {0}):
            choice = self._choice(index)
            choices.append(
                OpenAIStreamChoicePayload(
                    index=index,
                    finish_reason=choice.finish_reason,
                    content=choice.text.get_visible_text(),
                    reasoning_content=choice.text.get_thinking_text(),
                    tool_calls=choice.tool_calls.get_tool_calls(),
                    logprobs=deepcopy(choice.logprobs),
                )
            )
        result = build_openai_stream_result_payload(
            OpenAIStreamResultPayloadInputs(
                result_format=self._result_format,
                result_id=self._result_id,
                result_created_at=self._result_created_at,
                model=self._model,
                choices=choices,
                stored_usage=self._usage,
                override_usage=usage,
            )
        )
        self._result_id = result.result_id
        self._result_created_at = result.result_created_at
        if self._metrics is not None:
            result.payload["metrics"] = deepcopy(self._metrics)
        return result.payload
