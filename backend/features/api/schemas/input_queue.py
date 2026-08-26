"""SoAI - Input queue request schemas [backend/features/api/schemas/input_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from core.conversations.conversation_draft_content_validation import (
    CHAT_COMPOSER_TEXT_MAX_LENGTH,
)
from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.types.json import JSONDict, JSONValue
from core.validation.attachment_content import require_attachment_content_list
from core.validation.strings import coerce_optional_trimmed_str
from core.workspaces.soai_path_link_codec import extract_soai_path_tokens
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.shared_validation import (
    require_client_identifier,
    require_schema_text_field,
)

__all__ = ("InputQueueEnqueueRequest",)


def _require_input_type(value: str) -> str:
    normalized = require_schema_text_field(
        value,
        field_label="input_type",
        suffix="must be either 'prompt' or 'steer'.",
    ).lower()
    if normalized not in {"prompt", "steer"}:
        raise ValidationError("input_type must be either 'prompt' or 'steer'.")
    return normalized


def _require_attachment_content(value: list[JSONValue]) -> list[JSONDict]:
    return require_attachment_content_list(value)


class InputQueueEnqueueRequest(SoAIV1StrictModel):
    input_type: str = Field(..., min_length=1, max_length=16)
    text: str | None = Field(default=None, max_length=CHAT_COMPOSER_TEXT_MAX_LENGTH)
    prompt_history_text: str | None = Field(..., max_length=CHAT_COMPOSER_TEXT_MAX_LENGTH)
    attachment_content: list[PydanticJSONValue] = Field(default_factory=list[PydanticJSONValue])
    client_id: str = Field(..., min_length=1, max_length=128)
    client_request_id: str = Field(..., min_length=1, max_length=128)

    @field_validator("input_type")
    @classmethod
    def validate_input_type(cls, value: str) -> str:
        return _require_input_type(value)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return coerce_optional_trimmed_str(value)

    @field_validator("prompt_history_text")
    @classmethod
    def validate_prompt_history_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = coerce_optional_trimmed_str(value)
        if normalized is None:
            raise ValidationError("prompt_history_text must be non-empty when provided.")
        return normalized

    @field_validator("attachment_content")
    @classmethod
    def validate_attachment_content(cls, value: list[JSONValue]) -> list[JSONDict]:
        return _require_attachment_content(value)

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        return require_client_identifier(value)

    @field_validator("client_request_id")
    @classmethod
    def validate_client_request_id(cls, value: str) -> str:
        normalized = coerce_optional_trimmed_str(value)
        if normalized is None:
            raise ValidationError("client_request_id must be a non-empty string.")
        return normalized

    @model_validator(mode="after")
    def validate_payload(self) -> InputQueueEnqueueRequest:
        if self.text is None and not self.attachment_content:
            raise ValidationError("Input queue enqueue requires either text or attachment_content.")
        if self.text is not None and self.prompt_history_text is None:
            raise ValidationError("Textual inputs require prompt_history_text.")
        if (
            self.text is None
            and self.prompt_history_text is not None
            and not extract_soai_path_tokens(self.prompt_history_text)
        ):
            raise ValidationError("Attachment-only inputs cannot include prompt_history_text.")
        return self
