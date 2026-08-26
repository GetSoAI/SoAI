"""SoAI - Anthropic Messages request schemas [backend/features/api/schemas/anthropic_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, StrictBool, StrictInt, field_validator

from core.meta.soai_v1 import SoAIV1ExtensibleModel
from core.types.json import JSONValue
from core.validation.strings import require_trimmed_text
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.openai_numeric_validation import reject_boolean_numeric_value

__all__ = ("AnthropicCountTokensRequest", "AnthropicMessagesRequest")


class AnthropicCountTokensRequest(SoAIV1ExtensibleModel):
    model: str = Field(min_length=1)
    messages: list[dict[str, PydanticJSONValue]] = Field(min_length=1)
    system: str | list[dict[str, PydanticJSONValue]] | None = None
    tools: list[dict[str, PydanticJSONValue]] | None = None
    tool_choice: dict[str, PydanticJSONValue] | None = None
    thinking: dict[str, PydanticJSONValue] | None = None
    output_config: dict[str, PydanticJSONValue] | None = None
    context_management: dict[str, PydanticJSONValue] | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return require_trimmed_text(value, "Model must be a non-empty string.")


class AnthropicMessagesRequest(AnthropicCountTokensRequest):
    max_tokens: StrictInt = Field(gt=0, le=4_194_304)
    stream: StrictBool = False
    temperature: float | None = Field(None, ge=0.0, le=1.0)
    top_p: float | None = Field(None, ge=0.0, le=1.0)
    top_k: StrictInt | None = Field(None, ge=0)
    stop_sequences: list[str] | None = None
    metadata: dict[str, PydanticJSONValue] | None = None

    @field_validator("temperature", "top_p", mode="before")
    @classmethod
    def reject_boolean_float_fields(cls, value: JSONValue) -> JSONValue:
        return reject_boolean_numeric_value(value, message="Field must be numeric, not boolean.")
