"""SoAI - OpenAI inference request schemas [backend/features/api/schemas/openai_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, field_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.types.json import JSONValue
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.openai_audio import (
    CustomVoiceReference,
    normalize_audio_voice_reference,
)
from features.api.schemas.openai_base import BaseInferenceRequest, StreamOptions
from features.api.schemas.openai_chat_messages import (
    AssistantMessage,
    DeveloperMessage,
    FunctionMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from features.api.schemas.openai_prompt_cache import PromptCacheOptions
from features.api.schemas.openai_sampling import SamplingRequestBase

__all__ = (
    "ChatCompletionAudioParam",
    "ChatCompletionRequest",
    "CompletionRequest",
    "EmbeddingRequest",
)

OPENAI_MAX_OUTPUT_TOKENS = 4_194_304


class ChatCompletionAudioParam(SoAIV1StrictModel):
    voice: str | CustomVoiceReference
    format: Literal["wav", "aac", "mp3", "flac", "opus", "pcm16"]

    @field_validator("voice", mode="before")
    @classmethod
    def normalize_voice(cls, value: JSONValue) -> JSONValue:
        return normalize_audio_voice_reference(value)


class ChatCompletionRequest(BaseInferenceRequest, SamplingRequestBase):
    messages: list[
        Annotated[
            DeveloperMessage
            | SystemMessage
            | UserMessage
            | AssistantMessage
            | ToolMessage
            | FunctionMessage,
            Field(discriminator="role"),
        ]
    ] = Field(min_length=1)
    stream: StrictBool = False
    completion_count: StrictInt | None = Field(None, ge=1, le=128, alias="n")
    logprobs: StrictBool | None = False
    top_logprobs: StrictInt | None = Field(None, ge=0, le=20)
    tools: list[dict[str, PydanticJSONValue]] | None = None
    tool_choice: str | dict[str, PydanticJSONValue] | None = None
    functions: list[dict[str, PydanticJSONValue]] | None = None
    function_call: str | dict[str, PydanticJSONValue] | None = None
    parallel_tool_calls: StrictBool | None = None
    stream_options: StreamOptions | None = None
    store: StrictBool | None = None
    metadata: dict[str, PydanticJSONValue] | None = None
    prediction: dict[str, PydanticJSONValue] | None = None
    modalities: list[str] | None = None
    verbosity: Literal["low", "medium", "high"] | None = None
    audio: ChatCompletionAudioParam | None = None
    web_search_options: dict[str, PydanticJSONValue] | None = None
    max_tokens: StrictInt | None = Field(None, ge=0, le=OPENAI_MAX_OUTPUT_TOKENS)
    max_completion_tokens: StrictInt | None = Field(None, ge=0, le=OPENAI_MAX_OUTPUT_TOKENS)
    response_format: dict[str, PydanticJSONValue] | None = None
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] | None = (
        None
    )
    service_tier: Literal["auto", "default", "flex", "scale", "priority"] | None = None
    safety_identifier: str | None = None
    prompt_cache_key: str | None = None
    prompt_cache_options: PromptCacheOptions | None = None
    prompt_cache_retention: Literal["in_memory", "24h"] | None = None
    seed: StrictInt | None = None
    user: str | None = None


class CompletionRequest(BaseInferenceRequest, SamplingRequestBase):
    prompt: str | list[str] | list[int] | list[list[int]]
    stream: StrictBool = False
    stream_options: StreamOptions | None = None
    max_tokens: StrictInt | None = Field(None, ge=0, le=OPENAI_MAX_OUTPUT_TOKENS)
    completion_count: StrictInt | None = Field(None, ge=1, le=128, alias="n")
    suffix: str | None = None
    echo: StrictBool | None = False
    best_of: StrictInt | None = None
    logprobs: StrictInt | None = None
    seed: StrictInt | None = None
    user: str | None = None


class EmbeddingRequest(BaseInferenceRequest):
    input: (
        str
        | list[str]
        | Annotated[list[StrictInt], Field(min_length=1)]
        | Annotated[
            list[Annotated[list[StrictInt], Field(min_length=1)]],
            Field(min_length=1),
        ]
    )
    encoding_format: Literal["float", "base64"] | None = "float"
    dimensions: StrictInt | None = Field(None, gt=0)
    user: str | None = None

    @field_validator("input", mode="before")
    @classmethod
    def validate_embedding_input_non_empty(cls, value: JSONValue) -> JSONValue:
        if isinstance(value, str) and value == "":
            raise ValidationError("input must not be empty.")
        if isinstance(value, list) and not value:
            raise ValidationError("input list must not be empty.")
        if isinstance(value, list) and any(isinstance(item, str) and item == "" for item in value):
            raise ValidationError("input must not contain empty strings.")
        return value
