"""SoAI - Anthropic Messages response projection [backend/features/api/routes/anthropic/response_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.openai.sse_events import format_openai_sse_data
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.openai.tool_call_arguments import normalize_openai_tool_call_arguments
from core.openai.usage.resolution import resolve_canonical_usage
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.validation.json_schema import validate_json_schema_instance
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.api.routes.anthropic.stream_content import (
    SOAI_ANTHROPIC_THINKING_SIGNATURE,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AnthropicMessageProjectionSettings",
    "build_anthropic_message",
    "build_anthropic_message_from_openai_payload",
    "build_anthropic_usage",
)

_STRUCTURED_OUTPUT_TOOL_NAME = "soai_structured_output"


@dataclass(frozen=True, slots=True)
class AnthropicMessageProjectionSettings:
    model: str
    prompt_tokens: int
    prompt_token_counter: PromptTokenCounter
    structured_output_schema: JSONDict | None
    include_thinking: bool = False
    stop_sequences: list[str] | None = None


def _choice(payload: JSONDict) -> JSONDict:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise StateError("OpenAI completion response must contain exactly one choice.")
    return choices[0]


def _stop_result(
    finish_reason: JSONValue,
    tool_calls: list[JSONDict],
    stop_sequences: list[str] | None,
) -> tuple[str, str | None]:
    normalized = finish_reason.strip().lower() if isinstance(finish_reason, str) else ""
    if normalized in {"", "stop", "end_turn", "eos", "eos_token"}:
        return "end_turn", None
    if normalized in {"tool_calls", "function_call", "tool_use"}:
        return ("tool_use", None) if tool_calls else ("end_turn", None)
    if normalized in {"length", "max_tokens"}:
        return "max_tokens", None
    if normalized in {"content_filter", "refusal", "safety"}:
        return "refusal", None
    if normalized == "stop_sequence":
        matched_sequence = (
            stop_sequences[0] if stop_sequences is not None and len(stop_sequences) == 1 else None
        )
        return "stop_sequence", matched_sequence
    return "end_turn", None


def _tool_block(tool_call: JSONDict) -> JSONDict:
    function = tool_call.get("function")
    if not isinstance(function, dict):
        raise StateError("OpenAI tool call function payload is missing.")
    call_id = tool_call.get("id")
    name = function.get("name")
    if not isinstance(call_id, str) or not call_id or not isinstance(name, str) or not name:
        raise StateError("OpenAI tool call identity is incomplete.")
    arguments, _arguments_json, arguments_error = normalize_openai_tool_call_arguments(
        function.get("arguments"),
    )
    if arguments is None or arguments_error is not None:
        raise StateError("OpenAI tool call arguments are invalid.")
    return {"type": "tool_use", "id": call_id, "name": name, "input": arguments}


def _content_blocks(
    transcript: OpenAIStreamTranscript,
    *,
    structured_output_schema: JSONDict | None,
    include_thinking: bool,
    tool_content_anchors: dict[str, int] | None,
) -> list[JSONDict]:
    text = transcript.get_visible_text()
    tool_calls = transcript.get_tool_calls()
    if structured_output_schema is not None:
        if len(tool_calls) != 1:
            raise StateError("Structured output requires exactly one generated result.")
        function = tool_calls[0].get("function")
        if not isinstance(function, dict) or function.get("name") != _STRUCTURED_OUTPUT_TOOL_NAME:
            raise StateError("Structured output tool identity is invalid.")
        arguments, arguments_json, arguments_error = normalize_openai_tool_call_arguments(
            function.get("arguments"),
        )
        if arguments is None or arguments_error is not None:
            raise StateError("Structured output is not a valid JSON object.")
        try:
            validate_json_schema_instance(arguments, structured_output_schema)
        except ValidationError as exception:
            raise StateError(
                "Structured output does not satisfy the requested schema."
            ) from exception
        return [{"type": "text", "text": arguments_json}]
    blocks: list[JSONDict] = []
    thinking_text = transcript.get_thinking_text()
    if include_thinking and thinking_text:
        blocks.append(
            {
                "type": "thinking",
                "thinking": thinking_text,
                "signature": SOAI_ANTHROPIC_THINKING_SIGNATURE,
            }
        )
    cursor = 0
    for tool_call in tool_calls:
        call_id = tool_call.get("id")
        observed_anchor = (
            tool_content_anchors.get(call_id)
            if tool_content_anchors is not None and isinstance(call_id, str)
            else None
        )
        anchor = (
            observed_anchor
            if observed_anchor is not None
            else coerce_optional_non_negative_int_strict(tool_call.get("content_index_before"))
        )
        bounded_anchor = min(len(text), anchor if anchor is not None else len(text))
        if bounded_anchor > cursor:
            blocks.append({"type": "text", "text": text[cursor:bounded_anchor]})
        blocks.append(_tool_block(tool_call))
        cursor = bounded_anchor
    if cursor < len(text):
        blocks.append({"type": "text", "text": text[cursor:]})
    return blocks


def build_anthropic_usage(
    transcript: OpenAIStreamTranscript,
    *,
    prompt_tokens: int,
    prompt_token_counter: PromptTokenCounter,
    model: str,
) -> JSONDict:
    resolved = resolve_canonical_usage(
        transcript=transcript,
        explicit_usage_payload=transcript.get_reported_usage(),
        prompt_tokens_hint=prompt_tokens,
        prompt_token_counter=prompt_token_counter,
        model_name=model,
    ).usage
    reported_usage = transcript.get_reported_usage()
    prompt_details = (
        reported_usage.get("prompt_tokens_details") if isinstance(reported_usage, dict) else None
    )
    cached_tokens = (
        coerce_optional_non_negative_int_strict(prompt_details.get("cached_tokens"))
        if isinstance(prompt_details, dict)
        else None
    )
    cache_read_tokens = min(resolved.prompt_tokens, cached_tokens or 0)
    return {
        "input_tokens": resolved.prompt_tokens - cache_read_tokens,
        "output_tokens": resolved.completion_tokens,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": cache_read_tokens,
    }


def build_anthropic_message(
    transcript: OpenAIStreamTranscript,
    settings: AnthropicMessageProjectionSettings,
    *,
    tool_content_anchors: dict[str, int] | None = None,
) -> JSONDict:
    result = transcript.build_result_payload()
    choice = _choice(result)
    tool_calls = transcript.get_tool_calls()
    stop_reason, stop_sequence = (
        ("end_turn", None)
        if settings.structured_output_schema is not None
        else _stop_result(choice.get("finish_reason"), tool_calls, settings.stop_sequences)
    )
    return {
        "id": create_prefixed_hex_id("msg"),
        "type": "message",
        "role": "assistant",
        "model": settings.model,
        "content": _content_blocks(
            transcript,
            structured_output_schema=settings.structured_output_schema,
            include_thinking=settings.include_thinking,
            tool_content_anchors=tool_content_anchors,
        ),
        "stop_reason": stop_reason,
        "stop_sequence": stop_sequence,
        "usage": build_anthropic_usage(
            transcript,
            prompt_tokens=settings.prompt_tokens,
            prompt_token_counter=settings.prompt_token_counter,
            model=settings.model,
        ),
    }


def build_anthropic_message_from_openai_payload(
    payload: JSONDict,
    settings: AnthropicMessageProjectionSettings,
) -> JSONDict:
    transcript = OpenAIStreamTranscript(model_hint=settings.model)
    transcript.feed(format_openai_sse_data(payload))
    transcript.finalize()
    return build_anthropic_message(transcript, settings)
