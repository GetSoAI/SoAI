"""SoAI - Conversation API schemas [backend/features/api/schemas/conversations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from core.collections.ordered_uniqueness import unique_sequence
from core.conversations.conversation_identifier import CONVERSATION_ID_PATTERN_TEXT
from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.validation.strings import require_labeled_text
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.webui_chat_messages import WebUIChatMessage

__all__ = (
    "AgentCompactionBoundaryRemoveRequest",
    "AgentCompactionRegenerateRequest",
    "AgentCompactionStartRequest",
    "AgentShellToolStopRequest",
    "ConversationArchivedUpdate",
    "ConversationBatchDeleteRequest",
    "ConversationCloneRequest",
    "ConversationColorUpdate",
    "ConversationCreate",
    "ConversationFavoriteUpdate",
    "ConversationJsonExportRequest",
    "ConversationSettingsUpdate",
    "ConversationStreamCancelRequest",
    "ConversationStreamCancelResponse",
    "ConversationStreamStatusResponse",
    "ConversationUpdate",
    "MessageCursorMutationRequest",
    "MessageResubmitRequest",
    "MessagesUpdateRequest",
)


class ConversationCreate(SoAIV1StrictModel):
    id: StrictStr | None = Field(default=None, pattern=CONVERSATION_ID_PATTERN_TEXT)
    title: StrictStr = Field(..., min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return require_labeled_text(
            value,
            field_label="Conversation title",
            suffix="cannot be empty.",
        )


class ConversationCloneRequest(SoAIV1StrictModel):
    id: StrictStr | None = Field(default=None, pattern=CONVERSATION_ID_PATTERN_TEXT)


class ConversationBatchDeleteRequest(SoAIV1StrictModel):
    ids: list[StrictStr]

    @field_validator("ids")
    @classmethod
    def validate_ids(cls, value: list[str]) -> list[str]:
        unique_ids = list(unique_sequence((entry.strip() for entry in value), omit_falsy=True))
        if not unique_ids:
            raise ValidationError("At least one conversation id must be provided.")
        return unique_ids


class ConversationJsonExportRequest(SoAIV1StrictModel):
    active_model: StrictStr | None = Field(default=None, min_length=1, max_length=255)
    parameters: dict[str, PydanticJSONValue]


class ConversationUpdate(SoAIV1StrictModel):
    title: StrictStr = Field(..., min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return require_labeled_text(
            value,
            field_label="Conversation title",
            suffix="cannot be empty.",
        )


class ConversationSettingsUpdate(SoAIV1StrictModel):
    model_settings: dict[str, PydanticJSONValue]


class ConversationColorUpdate(SoAIV1StrictModel):
    color: StrictStr | None = Field(default=None)


class ConversationFavoriteUpdate(SoAIV1StrictModel):
    is_favorite: StrictBool


class ConversationArchivedUpdate(SoAIV1StrictModel):
    is_archived: StrictBool


class ConversationStreamStatusResponse(SoAIV1StrictModel):
    active: bool
    conversation_id: str
    start_admission: Literal["inactive", "busy", "unknown"] = "unknown"
    stream_lifecycle: Literal["inactive", "streaming", "terminalizing"]
    can_accept_conversation_input: bool
    can_start_next_prompt: bool
    can_accept_steer_prompt: bool
    active_tool_call_count: int
    request_id: str | None = None
    assistant_at_ms: int | None = None
    assistant_turn_at_ms: int | None = None
    model_variant_index: int | None = None
    model_id: str | None = None
    preview_key: str | None = None
    preview_args: dict[str, PydanticJSONValue] | None = None
    preview_generated_at_ms: int | None = None
    preview_cooldown_ms: int | None = None
    preview_trigger: str | None = None


class ConversationStreamCancelRequest(SoAIV1StrictModel):
    request_id: StrictStr = Field(..., min_length=1, max_length=512)
    force_pending_steers: StrictBool

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return require_labeled_text(
            value,
            field_label="Chat stream request id",
            suffix="is required.",
        )


class ConversationStreamCancelResponse(SoAIV1StrictModel):
    conversation_id: StrictStr
    request_id: StrictStr
    status: Literal["cancellation_requested", "already_terminal", "superseded"]


class AgentCompactionStartRequest(SoAIV1StrictModel):
    model: StrictStr = Field(..., min_length=1, max_length=255)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return require_labeled_text(value, field_label="Compaction model", suffix="is required.")


class AgentCompactionRegenerateRequest(SoAIV1StrictModel):
    assistant_turn_at_ms: StrictInt = Field(..., gt=0)
    client_id: StrictStr | None = Field(default=None, min_length=1, max_length=128)
    client_request_id: StrictStr | None = Field(default=None, min_length=1, max_length=128)
    expected_last_modified_at_ms: StrictInt | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_idempotency_fields(self) -> AgentCompactionRegenerateRequest:
        fields = (
            self.client_id,
            self.client_request_id,
            self.expected_last_modified_at_ms,
        )
        if any(value is not None for value in fields) and not all(
            value is not None for value in fields
        ):
            raise ValidationError(
                "Compaction regeneration identity and revision must be supplied together."
            )
        return self


class AgentCompactionBoundaryRemoveRequest(SoAIV1StrictModel):
    assistant_turn_at_ms: StrictInt = Field(..., gt=0)
    model_variant_index: StrictInt = Field(..., ge=0)
    tool_call_id: StrictStr = Field(..., min_length=1)
    expected_last_modified_at_ms: StrictInt = Field(..., ge=1)

    @field_validator("tool_call_id")
    @classmethod
    def validate_tool_call_id(cls, value: str) -> str:
        return require_labeled_text(value, field_label="Tool call id", suffix="is required.")


class AgentShellToolStopRequest(SoAIV1StrictModel):
    assistant_turn_at_ms: StrictInt = Field(..., gt=0)
    model_variant_index: StrictInt = Field(..., ge=0)
    tool_call_id: StrictStr = Field(..., min_length=1)

    @field_validator("tool_call_id")
    @classmethod
    def validate_tool_call_id(cls, value: str) -> str:
        return require_labeled_text(value, field_label="Tool call id", suffix="is required.")


class MessagesUpdateRequest(SoAIV1StrictModel):
    expected_last_modified_at_ms: StrictInt = Field(..., ge=1)
    messages: list[WebUIChatMessage]


class MessageCursorMutationRequest(SoAIV1StrictModel):
    expected_last_modified_at_ms: StrictInt = Field(..., ge=1)
    created_at_ms: StrictInt = Field(..., ge=1)
    message_id: StrictInt = Field(..., ge=0)


class MessageResubmitRequest(MessageCursorMutationRequest):
    message: WebUIChatMessage
