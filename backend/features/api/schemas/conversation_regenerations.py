"""SoAI - Conversation regeneration request schemas [backend/features/api/schemas/conversation_regenerations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.validation.strings import coerce_optional_trimmed_str
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.shared_validation import require_client_identifier

__all__ = ("ConversationMessageRegenerateRequest", "ConversationRegenerationCursor")


class ConversationRegenerationCursor(SoAIV1StrictModel):
    created_at_ms: StrictInt = Field(..., ge=1)
    message_id: StrictInt = Field(..., ge=0)


class ConversationMessageRegenerateRequest(SoAIV1StrictModel):
    client_id: StrictStr = Field(..., min_length=1, max_length=128)
    client_request_id: StrictStr = Field(..., min_length=1, max_length=128)
    expected_last_modified_at_ms: StrictInt = Field(..., ge=1)
    target: ConversationRegenerationCursor | None = None
    retry_input_id: StrictStr | None = Field(default=None, min_length=1, max_length=128)
    content_preview_feedback: dict[str, PydanticJSONValue] | None = None
    preview_contract_feedback: dict[str, PydanticJSONValue] | None = None

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        return require_client_identifier(value)

    @field_validator("client_request_id", "retry_input_id")
    @classmethod
    def validate_optional_identity(cls, value: str | None) -> str | None:
        normalized = coerce_optional_trimmed_str(value)
        if value is not None and normalized is None:
            raise ValidationError("Conversation regeneration identity must be non-empty.")
        return normalized

    @model_validator(mode="after")
    def validate_target(self) -> ConversationMessageRegenerateRequest:
        if (self.target is None) == (self.retry_input_id is None):
            raise ValidationError(
                "Conversation regeneration requires exactly one target or retry_input_id.",
            )
        return self
