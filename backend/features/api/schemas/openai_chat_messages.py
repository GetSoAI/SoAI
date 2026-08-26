"""SoAI - OpenAI chat message schemas [backend/features/api/schemas/openai_chat_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.openai_prompt_cache import PromptCacheBreakpoint
from features.api.schemas.shared_validation import (
    require_non_empty_content_when_list,
    require_non_empty_schema_sequence,
)

__all__ = (
    "AssistantMessage",
    "ChatContentFileObject",
    "ChatContentFilePart",
    "ChatContentImageURLDetail",
    "ChatContentImageURLPart",
    "ChatContentInputAudio",
    "ChatContentInputAudioPart",
    "ChatContentRefusalPart",
    "ChatContentTextPart",
    "DeveloperMessage",
    "FunctionMessage",
    "SystemMessage",
    "ToolMessage",
    "UserMessage",
)


class ChatContentTextPart(SoAIV1StrictModel):
    type: Literal["text"]
    text: str
    prompt_cache_breakpoint: PromptCacheBreakpoint | None = None


class ChatContentRefusalPart(SoAIV1StrictModel):
    type: Literal["refusal"]
    refusal: str
    prompt_cache_breakpoint: PromptCacheBreakpoint | None = None


class ChatContentImageURLDetail(SoAIV1StrictModel):
    url: str
    detail: Literal["auto", "low", "high"] | None = "auto"


class ChatContentImageURLPart(SoAIV1StrictModel):
    type: Literal["image_url"]
    image_url: ChatContentImageURLDetail
    prompt_cache_breakpoint: PromptCacheBreakpoint | None = None


class ChatContentInputAudio(SoAIV1StrictModel):
    data: str
    format: Literal["wav", "mp3"]


class ChatContentInputAudioPart(SoAIV1StrictModel):
    type: Literal["input_audio"]
    input_audio: ChatContentInputAudio
    prompt_cache_breakpoint: PromptCacheBreakpoint | None = None


class ChatContentFileObject(SoAIV1StrictModel):
    filename: str | None = None
    file_data: str | None = None
    file_id: str | None = None


class ChatContentFilePart(SoAIV1StrictModel):
    type: Literal["file"]
    file: ChatContentFileObject
    prompt_cache_breakpoint: PromptCacheBreakpoint | None = None


class DeveloperMessage(SoAIV1StrictModel):
    role: Literal["developer"] = "developer"
    content: str | list[ChatContentTextPart]
    name: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        require_non_empty_content_when_list(self.content)
        return self


class SystemMessage(SoAIV1StrictModel):
    role: Literal["system"] = "system"
    content: str | list[ChatContentTextPart]
    name: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        require_non_empty_content_when_list(self.content)
        return self


class UserMessage(SoAIV1StrictModel):
    role: Literal["user"] = "user"
    content: (
        str
        | list[
            ChatContentFilePart
            | ChatContentImageURLPart
            | ChatContentInputAudioPart
            | ChatContentTextPart
        ]
    )
    name: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        require_non_empty_content_when_list(self.content)
        return self


class AssistantMessage(SoAIV1StrictModel):
    role: Literal["assistant"] = "assistant"
    content: str | list[ChatContentTextPart | ChatContentRefusalPart] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=256)
    tool_calls: list[dict[str, PydanticJSONValue]] | None = None
    function_call: dict[str, PydanticJSONValue] | None = None
    refusal: str | None = None
    audio: dict[str, PydanticJSONValue] | None = None
    reasoning_content: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if self.content is None:
            has_tool_calls = isinstance(self.tool_calls, list) and bool(self.tool_calls)
            has_function_call = isinstance(self.function_call, dict) and bool(self.function_call)
            if not has_tool_calls and not has_function_call:
                raise ValidationError(
                    "content is required unless tool_calls or function_call are provided.",
                )
            return self
        content_parts = self.content
        if isinstance(content_parts, list):
            parts = list(content_parts)
            require_non_empty_schema_sequence(parts, label="content")
            observed_types_list: list[str] = []
            for part in parts:
                observed_types_list.append(part.type)
            observed_types = tuple(observed_types_list)
            if "refusal" in observed_types and (
                len(observed_types) != 1 or observed_types[0] != "refusal"
            ):
                raise ValidationError("refusal content must be provided as a single refusal part.")
        return self


class ToolMessage(SoAIV1StrictModel):
    role: Literal["tool"] = "tool"
    content: str | list[ChatContentTextPart]
    tool_call_id: str = Field(..., min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        require_non_empty_content_when_list(self.content)
        return self


class FunctionMessage(SoAIV1StrictModel):
    role: Literal["function"] = "function"
    content: str | None
    name: str = Field(..., min_length=1, max_length=256)
