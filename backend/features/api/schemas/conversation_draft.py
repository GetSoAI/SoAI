"""SoAI - Conversation draft request schemas [backend/features/api/schemas/conversation_draft.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from core.conversations.conversation_draft_content_validation import (
    CHAT_COMPOSER_TEXT_MAX_LENGTH,
    validate_conversation_draft_entries,
)
from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.types.json import JSONValue
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.shared_validation import require_client_identifier

__all__ = ("ConversationDraftSaveRequest",)


class ConversationDraftSaveRequest(SoAIV1StrictModel):
    text: str | None = Field(default=None, max_length=CHAT_COMPOSER_TEXT_MAX_LENGTH)
    source_text: str = Field(..., max_length=CHAT_COMPOSER_TEXT_MAX_LENGTH)
    attachment_content: list[PydanticJSONValue] = Field(default_factory=list[PydanticJSONValue])
    client_id: str = Field(..., min_length=1, max_length=128)
    client_sequence: int = Field(..., ge=0)
    base_revision: int = Field(..., ge=0)

    @field_validator("attachment_content")
    @classmethod
    def validate_attachment_content(cls, value: list[JSONValue]) -> list[JSONValue]:
        return validate_conversation_draft_entries(value)

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        return require_client_identifier(value)

    @model_validator(mode="after")
    def validate_non_empty(self) -> ConversationDraftSaveRequest:
        if self.text in (None, "") and not self.attachment_content:
            raise ValidationError("Conversation draft requires text or attachment_content.")
        if self.text in (None, "") and self.source_text:
            raise ValidationError("Conversation draft source_text requires displayed text.")
        return self
