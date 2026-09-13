"""SoAI - OpenAI stream transcript result payload assembly [backend/core/openai/stream_transcript/result_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.openai.usage.serialization import extract_public_usage_payload
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.timing.epoch import epoch_seconds

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OpenAIStreamChoicePayload",
    "OpenAIStreamResultPayload",
    "OpenAIStreamResultPayloadInputs",
    "build_openai_stream_result_payload",
)


@dataclass(frozen=True, slots=True)
class OpenAIStreamChoicePayload:
    index: int
    finish_reason: str | None
    content: str
    reasoning_content: str
    tool_calls: list[JSONDict]
    logprobs: JSONDict | None = None


@dataclass(frozen=True, slots=True)
class OpenAIStreamResultPayloadInputs:
    result_format: Literal["chat", "completions"]
    result_id: str | None
    result_created_at: int | None
    model: str | None
    choices: list[OpenAIStreamChoicePayload]
    stored_usage: JSONDict | None
    override_usage: JSONDict | None


@dataclass(frozen=True, slots=True)
class OpenAIStreamResultPayload:
    payload: JSONDict
    result_id: str
    result_created_at: int


def _resolve_usage_payload(inputs: OpenAIStreamResultPayloadInputs) -> JSONDict | None:
    usage_payload: JSONDict | None = None
    if inputs.override_usage is not None:
        usage_payload = extract_public_usage_payload(inputs.override_usage)
    if usage_payload is None and inputs.stored_usage is not None:
        usage_payload = dict(inputs.stored_usage)
    return usage_payload


def _resolve_created_at(value: int | None) -> int:
    if value is None:
        return int(epoch_seconds())
    return value


def _build_completion_choice(choice: OpenAIStreamChoicePayload) -> JSONDict:
    return {
        "index": choice.index,
        "text": choice.content,
        "logprobs": choice.logprobs,
        "finish_reason": choice.finish_reason or "stop",
    }


def _build_chat_choice(choice: OpenAIStreamChoicePayload) -> JSONDict:
    message: JSONDict = {"role": "assistant", "content": choice.content}
    if choice.reasoning_content:
        message["reasoning_content"] = choice.reasoning_content
        message["reasoning"] = choice.reasoning_content
    if choice.tool_calls:
        message["tool_calls"] = [dict(tool_call) for tool_call in choice.tool_calls]
    payload: JSONDict = {
        "index": choice.index,
        "message": message,
        "finish_reason": choice.finish_reason or "stop",
    }
    if choice.logprobs is not None:
        payload["logprobs"] = choice.logprobs
    return payload


def build_openai_stream_result_payload(
    inputs: OpenAIStreamResultPayloadInputs,
) -> OpenAIStreamResultPayload:
    usage_payload = _resolve_usage_payload(inputs)
    result_created_at = _resolve_created_at(inputs.result_created_at)
    is_chat = inputs.result_format == "chat"
    result_id = inputs.result_id or create_prefixed_hex_id(
        "chatcmpl" if is_chat else "cmpl", separator="-"
    )
    payload: JSONDict = {
        "id": result_id,
        "object": "chat.completion" if is_chat else "text_completion",
        "created": result_created_at,
        "model": inputs.model or "unknown",
        "choices": [
            _build_chat_choice(choice) if is_chat else _build_completion_choice(choice)
            for choice in inputs.choices
        ],
    }
    if usage_payload is not None:
        payload["usage"] = usage_payload
    return OpenAIStreamResultPayload(
        payload=payload, result_id=result_id, result_created_at=result_created_at
    )
