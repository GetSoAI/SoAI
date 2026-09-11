"""SoAI - WebUI chat message schemas [backend/features/api/schemas/webui_chat_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt, model_validator

from core.attachments.attachment_content_validation import (
    validate_soai_file_content_part,
    validate_soai_file_unavailable_content_part,
    validate_soai_knowledge_content_part,
    validate_soai_knowledge_unavailable_content_part,
)
from core.conversations.conversation_message_role_fields import (
    validate_webui_chat_message_role_fields,
)
from core.meta.soai_v1 import SoAIV1StrictModel
from core.timing.epoch import epoch_ms
from core.validation.epoch import EPOCH_MS_MIN
from core.workspaces.soai_path_content_validation import validate_soai_path_content_part
from features.api.schemas.json_fields import PydanticJSONValue
from features.api.schemas.openai_chat_messages import (
    ChatContentFilePart,
    ChatContentImageURLPart,
    ChatContentInputAudioPart,
    ChatContentRefusalPart,
    ChatContentTextPart,
)

__all__ = (
    "ChatContentSoaiFilePart",
    "ChatContentSoaiFileUnavailablePart",
    "ChatContentSoaiKnowledgePart",
    "ChatContentSoaiKnowledgeUnavailablePart",
    "ChatContentSoaiPathPart",
    "WebUIChatMessage",
)


class ChatContentSoaiPathSourceReference(SoAIV1StrictModel):
    type: Literal["conversation_virtual_path"]
    value: str = Field(min_length=1, max_length=2048)


class ChatContentSoaiPathToolReference(SoAIV1StrictModel):
    type: Literal["workspace_relative_path"]
    value: str = Field(min_length=1, max_length=2048)


class ChatContentSoaiPathWorkspaceScope(SoAIV1StrictModel):
    type: Literal["conversation_effective_workspace"]
    root_fingerprint: str = Field(min_length=1, max_length=128)


class ChatContentSoaiPathTargetFingerprint(SoAIV1StrictModel):
    type: Literal["file_sha256", "folder_listing_sha256"]
    value: str = Field(min_length=71, max_length=71)


class ChatContentSoaiPathPart(SoAIV1StrictModel):
    type: Literal["soai_path"]
    entry_type: Literal["file", "folder"]
    source_reference: ChatContentSoaiPathSourceReference
    tool_reference: ChatContentSoaiPathToolReference
    workspace_scope: ChatContentSoaiPathWorkspaceScope
    target_fingerprint: ChatContentSoaiPathTargetFingerprint
    title: str = Field(min_length=1, max_length=512)
    preview_type: Literal["text", "folder", "image", "audio", "video", "document", "file"]
    mime_type: str | None = Field(default=None, min_length=1, max_length=256)
    size_bytes: StrictInt | None = Field(ge=0)
    modified_at_ms: StrictInt = Field(ge=EPOCH_MS_MIN)
    resolved_at_ms: StrictInt = Field(ge=EPOCH_MS_MIN)

    @model_validator(mode="after")
    def validate_canonical_part(self) -> ChatContentSoaiPathPart:
        validate_soai_path_content_part(self.model_dump())
        return self


class ChatContentSoaiFilePart(SoAIV1StrictModel):
    type: Literal["soai_file"]
    attachment_id: str = Field(min_length=1, max_length=128)
    file_id: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=256)
    size_bytes: StrictInt = Field(ge=0)
    preview_type: Literal["text", "image", "audio", "video", "document", "file"]
    attachment_revision: StrictInt = Field(ge=0)
    created_at_ms: StrictInt = Field(ge=EPOCH_MS_MIN)

    @model_validator(mode="after")
    def validate_canonical_part(self) -> ChatContentSoaiFilePart:
        validate_soai_file_content_part(self.model_dump())
        return self


class ChatContentSoaiFileUnavailablePart(SoAIV1StrictModel):
    type: Literal["soai_file_unavailable"]
    filename: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=256)
    size_bytes: StrictInt = Field(ge=0)
    preview_type: Literal["text", "image", "audio", "video", "document", "file"]
    reason: Literal["source_attachment_unavailable"]

    @model_validator(mode="after")
    def validate_canonical_part(self) -> ChatContentSoaiFileUnavailablePart:
        validate_soai_file_unavailable_content_part(self.model_dump())
        return self


class ChatContentSoaiKnowledgePart(SoAIV1StrictModel):
    type: Literal["soai_knowledge"]
    knowledge_attachment_id: str = Field(min_length=1, max_length=128)
    summary_id: str = Field(min_length=1, max_length=128)
    source_type: Literal[
        "composer_document_upload",
        "composer_folder_upload",
        "knowledge_tab_document_upload",
        "knowledge_tab_folder_upload",
        "file_explorer_folder_import",
        "document_delete",
        "bulk_delete",
        "reindex",
        "linked_knowledge",
    ]
    operation_type: Literal["added", "removed", "updated", "reindexed"]
    title: str = Field(min_length=1, max_length=512)
    total_count: StrictInt = Field(ge=0)
    visible_count: StrictInt = Field(ge=0)
    hidden_count: StrictInt = Field(ge=0)
    status_counts: dict[str, StrictInt]
    attachment_revision: StrictInt = Field(ge=0)
    first_event_id: StrictInt | None = Field(default=None, ge=0)
    last_event_id: StrictInt | None = Field(default=None, ge=0)
    created_at_ms: StrictInt = Field(ge=EPOCH_MS_MIN)
    finalized_at_ms: StrictInt = Field(ge=EPOCH_MS_MIN)

    @model_validator(mode="after")
    def validate_canonical_part(self) -> ChatContentSoaiKnowledgePart:
        validate_soai_knowledge_content_part(self.model_dump())
        return self


class ChatContentSoaiKnowledgeUnavailablePart(SoAIV1StrictModel):
    type: Literal["soai_knowledge_unavailable"]
    title: str = Field(min_length=1, max_length=512)
    source_type: Literal[
        "composer_document_upload",
        "composer_folder_upload",
        "knowledge_tab_document_upload",
        "knowledge_tab_folder_upload",
        "file_explorer_folder_import",
        "document_delete",
        "bulk_delete",
        "reindex",
        "linked_knowledge",
    ]
    reason: Literal["source_attachment_unavailable"]

    @model_validator(mode="after")
    def validate_canonical_part(self) -> ChatContentSoaiKnowledgeUnavailablePart:
        validate_soai_knowledge_unavailable_content_part(self.model_dump())
        return self


class WebUIChatMessage(SoAIV1StrictModel):
    role: Literal["system", "developer", "user", "assistant", "tool"]
    message_type: Literal["chat"] = Field(default="chat", exclude=True)
    timestamp: StrictInt = Field(default_factory=epoch_ms, ge=EPOCH_MS_MIN)
    assistant_turn_at_ms: StrictInt | None = Field(default=None, ge=EPOCH_MS_MIN)
    model_variant_index: StrictInt | None = Field(default=None, ge=0)
    content: (
        str
        | list[
            ChatContentTextPart
            | ChatContentImageURLPart
            | ChatContentInputAudioPart
            | ChatContentFilePart
            | ChatContentRefusalPart
            | ChatContentSoaiPathPart
            | ChatContentSoaiFilePart
            | ChatContentSoaiFileUnavailablePart
            | ChatContentSoaiKnowledgePart
            | ChatContentSoaiKnowledgeUnavailablePart
        ]
        | None
    ) = None
    name: str | None = Field(default=None, min_length=1, max_length=256)
    tool_call_id: str | None = Field(default=None, min_length=1, max_length=128)
    tool_calls: list[dict[str, PydanticJSONValue]] | None = None
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    model_id: str | None = Field(default=None, max_length=256)
    prompt_tokens: StrictInt | None = Field(default=None, ge=0)
    completion_tokens: StrictInt | None = Field(default=None, ge=0)
    total_tokens: StrictInt | None = Field(default=None, ge=0)
    usage_source: str | None = Field(default=None, min_length=1, max_length=64)
    generation_latency_ms: StrictInt | None = Field(default=None, ge=0)
    finish_reason: str | None = Field(default=None, max_length=64)
    thinking_tail_duration_ms: StrictInt | None = Field(default=None, ge=0)
    assistant_event_timeline: list[dict[str, PydanticJSONValue]] | None = None

    @model_validator(mode="after")
    def validate_role_fields(self) -> WebUIChatMessage:
        field_names = frozenset(str(field_name) for field_name in self.model_fields_set)
        validate_webui_chat_message_role_fields(
            role=self.role,
            field_names=field_names,
            content_present="content" in field_names,
            content_is_none=self.content is None,
            assistant_event_timeline_present="assistant_event_timeline" in field_names,
            assistant_turn_at_ms_present="assistant_turn_at_ms" in field_names,
            assistant_turn_at_ms_is_none=self.assistant_turn_at_ms is None,
            model_variant_index_present="model_variant_index" in field_names,
            model_variant_index_is_none=self.model_variant_index is None,
            tool_call_id_present="tool_call_id" in field_names,
            tool_call_id=self.tool_call_id,
            tool_calls_present="tool_calls" in field_names,
        )
        return self
