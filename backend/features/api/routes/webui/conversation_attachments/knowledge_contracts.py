"""SoAI - WebUI knowledge attachment route contracts [backend/features/api/routes/webui/conversation_attachments/knowledge_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from features.api.schemas.shared_validation import require_schema_text_field

__all__ = (
    "KnowledgeAttachmentClaimRequest",
    "KnowledgeAttachmentItemPreviewRequest",
    "KnowledgeAttachmentItemsRequest",
    "KnowledgeAttachmentReusableRequest",
    "KnowledgeAttachmentSelection",
    "KnowledgeAttachmentUseRequest",
    "KnowledgeAttachmentUseSelection",
)


class KnowledgeAttachmentSelection(SoAIV1StrictModel):
    knowledge_attachment_id: str = Field(..., min_length=1, max_length=128)
    attachment_revision: int = Field(..., ge=0)

    @field_validator("knowledge_attachment_id")
    @classmethod
    def validate_knowledge_attachment_id(cls, value: str) -> str:
        return require_schema_text_field(
            value,
            field_label="knowledge_attachment_id",
            suffix="must be a non-empty string.",
        )


class KnowledgeAttachmentClaimRequest(SoAIV1StrictModel):
    selections: list[KnowledgeAttachmentSelection] = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_selections(self) -> KnowledgeAttachmentClaimRequest:
        seen: set[str] = set()
        for selection in self.selections:
            if selection.knowledge_attachment_id in seen:
                raise ValidationError("Knowledge attachment selections must be unique.")
            seen.add(selection.knowledge_attachment_id)
        return self


class KnowledgeAttachmentItemPreviewRequest(SoAIV1StrictModel):
    document_id: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_schema_text_field(
            value,
            field_label="document_id",
            suffix="must be a non-empty string.",
        )


class KnowledgeAttachmentItemsRequest(SoAIV1StrictModel):
    limit: int = Field(default=50, ge=1, le=200)
    cursor_item_index: int | None = Field(default=None, ge=0)
    cursor_id: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, min_length=1, max_length=64)
    query: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return require_schema_text_field(
            normalized,
            field_label="query",
            suffix="must be a non-empty string.",
        )


class KnowledgeAttachmentReusableRequest(SoAIV1StrictModel):
    query: str | None = Field(default=None, min_length=1, max_length=256)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return require_schema_text_field(
            normalized,
            field_label="query",
            suffix="must be a non-empty string.",
        )


class KnowledgeAttachmentUseSelection(SoAIV1StrictModel):
    item_id: int = Field(..., ge=1)
    document_id: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_schema_text_field(
            value,
            field_label="document_id",
            suffix="must be a non-empty string.",
        )


class KnowledgeAttachmentUseRequest(SoAIV1StrictModel):
    source_conv_id: str = Field(..., min_length=1, max_length=128)
    source_knowledge_attachment_id: str = Field(..., min_length=1, max_length=128)
    selections: list[KnowledgeAttachmentUseSelection] = Field(..., min_length=1)
    client_batch_id: str = Field(..., min_length=1, max_length=128)

    @field_validator("source_conv_id", "source_knowledge_attachment_id", "client_batch_id")
    @classmethod
    def validate_text_field(cls, value: str) -> str:
        return require_schema_text_field(
            value,
            field_label="linked knowledge field",
            suffix="must be a non-empty string.",
        )

    @model_validator(mode="after")
    def validate_unique_selections(self) -> KnowledgeAttachmentUseRequest:
        item_ids: set[int] = set()
        document_ids: set[str] = set()
        for selection in self.selections:
            if selection.item_id in item_ids:
                raise ValidationError("Linked knowledge item selections must be unique.")
            item_ids.add(selection.item_id)
            if selection.document_id is not None:
                if selection.document_id in document_ids:
                    raise ValidationError("Linked knowledge document selections must be unique.")
                document_ids.add(selection.document_id)
        return self
