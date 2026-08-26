"""SoAI - OpenAI Responses request and response schemas [backend/features/api/schemas/openai_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.types.json import JSONValue
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.openai_base import StreamOptions
from features.api.schemas.openai_numeric_validation import reject_boolean_numeric_value
from features.api.schemas.openai_prompt_cache import PromptCacheOptions

__all__ = (
    "ResponsesInputItem",
    "ResponsesOutputContent",
    "ResponsesOutputItem",
    "ResponsesRequest",
    "ResponsesResponse",
)

OPENAI_RESPONSES_MAX_OUTPUT_TOKENS = 4_194_304


class ResponsesInputItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str = "message"
    role: str | None = None
    content: str | list[dict[str, PydanticJSONValue]] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=256)
    call_id: str | None = None
    arguments: str | None = None
    output: str | list[dict[str, PydanticJSONValue]] | None = None
    id: str | None = None
    status: str | None = None


class ResponsesRequest(SoAIV1StrictModel):
    model: StrictStr | None = None
    input: StrictStr | list[ResponsesInputItem] | None = None
    instructions: StrictStr | None = None
    previous_response_id: StrictStr | None = None
    truncation: StrictStr | None = Field(None, pattern="^(auto|disabled)$")
    stream: StrictBool | None = False
    parallel_tool_calls: StrictBool | None = True
    store: StrictBool | None = True
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    top_p: float | None = Field(None, ge=0.0, le=1.0)
    reasoning: dict[str, PydanticJSONValue] | None = None
    include: list[StrictStr] | None = None
    stream_options: StreamOptions | None = None
    conversation: StrictStr | dict[str, PydanticJSONValue] | None = None
    client_metadata: dict[str, PydanticJSONValue] | None = None
    context_management: list[dict[str, PydanticJSONValue]] | None = None
    prompt: dict[str, PydanticJSONValue] | None = None
    max_output_tokens: StrictInt | None = Field(None, ge=0, le=OPENAI_RESPONSES_MAX_OUTPUT_TOKENS)
    max_tool_calls: StrictInt | None = Field(None, ge=0, le=128)
    metadata: dict[str, PydanticJSONValue] | None = None
    text: dict[str, PydanticJSONValue] | None = None
    top_logprobs: StrictInt | None = Field(None, ge=0, le=20)
    tools: list[dict[str, PydanticJSONValue]] | None = None
    tool_choice: StrictStr | dict[str, PydanticJSONValue] | None = None
    background: StrictBool | None = None
    prompt_cache_key: StrictStr | None = None
    prompt_cache_options: PromptCacheOptions | None = None
    prompt_cache_retention: StrictStr | None = None
    safety_identifier: StrictStr | None = None
    service_tier: StrictStr | None = None
    user: StrictStr | None = None

    @field_validator("temperature", "top_p", mode="before")
    @classmethod
    def reject_boolean_float_fields(cls, value: JSONValue) -> JSONValue:
        return reject_boolean_numeric_value(value, message="Field must be numeric, not boolean.")

    @model_validator(mode="after")
    def validate_responses_request_flags(self) -> ResponsesRequest:
        if self.background is True and self.store is False:
            raise ValidationError("background requests require store=true.")
        if self.stream_options is not None and self.stream is not True:
            raise ValidationError("stream_options is only supported when stream=true.")
        if self.stream_options is not None and self.stream_options.include_usage is not None:
            raise ValidationError(
                "stream_options.include_usage is not supported for Responses requests.",
            )
        return self


class ResponsesOutputContent(BaseModel):
    type: str = "output_text"
    text: str = ""
    annotations: list[PydanticJSONValue] = Field(default_factory=list[PydanticJSONValue])


class ResponsesOutputItem(BaseModel):
    type: str = "message"
    id: str
    status: str = "completed"
    role: str = "assistant"
    content: list[ResponsesOutputContent] = Field(default_factory=list[ResponsesOutputContent])


class ResponsesResponse(BaseModel):
    id: str
    object: str = "response"
    created_at: int
    status: str = "completed"
    error: dict[str, PydanticJSONValue] | None = None
    incomplete_details: dict[str, PydanticJSONValue] | None = None
    instructions: str | None = None
    max_output_tokens: int | None = None
    model: str
    output: list[ResponsesOutputItem]
    parallel_tool_calls: StrictBool = True
    previous_response_id: str | None = None
    reasoning: dict[str, PydanticJSONValue] | None = None
    temperature: float | None = None
    top_p: float | None = None
    usage: dict[str, PydanticJSONValue] | None = None
