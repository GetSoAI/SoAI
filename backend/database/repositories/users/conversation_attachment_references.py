"""SoAI - Message attachment reference extraction [backend/database/repositories/users/conversation_attachment_references.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.attachments.attachment_content_validation import (
    validate_soai_file_content_part,
    validate_soai_knowledge_content_part,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_optional_non_negative_int_strict,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "ConversationAttachmentReferences",
    "FileAttachmentReference",
    "KnowledgeAttachmentReference",
    "extract_content_attachment_references",
    "extract_message_attachment_references",
)


@dataclass(frozen=True, slots=True)
class FileAttachmentReference:
    attachment_id: str
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int
    preview_type: str
    attachment_revision: int
    created_at_ms: int
    message_created_at_ms: int


@dataclass(frozen=True, slots=True)
class KnowledgeAttachmentReference:
    knowledge_attachment_id: str
    summary_id: str
    source_type: str
    operation_type: str
    title: str
    total_count: int
    visible_count: int
    hidden_count: int
    status_counts: JSONDict
    attachment_revision: int
    first_event_id: int | None
    last_event_id: int | None
    created_at_ms: int
    finalized_at_ms: int
    message_created_at_ms: int


@dataclass(frozen=True, slots=True)
class ConversationAttachmentReferences:
    files: list[FileAttachmentReference] = field(default_factory=list[FileAttachmentReference])
    knowledge: list[KnowledgeAttachmentReference] = field(
        default_factory=list[KnowledgeAttachmentReference],
    )


def _validated_non_negative_int(validated: JSONDict, field_name: str) -> int:
    return require_non_negative_int_strict(
        validated[field_name],
        error_message=f"Validated SoAI attachment {field_name} must be a non-negative integer.",
    )


def _validated_optional_non_negative_int(validated: JSONDict, field_name: str) -> int | None:
    return require_optional_non_negative_int_strict(
        validated[field_name],
        error_message=f"Validated SoAI attachment {field_name} must be a non-negative integer.",
    )


def _validated_epoch_ms(validated: JSONDict, field_name: str) -> int:
    return require_unix_epoch_ms(
        validated[field_name],
        error_message=f"Validated SoAI attachment {field_name} must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )


def _validated_status_counts(validated: JSONDict) -> JSONDict:
    status_counts = coerce_json_dict(validated["status_counts"])
    if status_counts is None:
        raise ValidationError("Validated SoAI knowledge status_counts must be an object.")
    return status_counts


def _extract_file_reference(
    part: JSONDict,
    *,
    message_created_at_ms: int,
) -> FileAttachmentReference:
    validated = validate_soai_file_content_part(part)
    return FileAttachmentReference(
        attachment_id=str(validated["attachment_id"]),
        file_id=str(validated["file_id"]),
        filename=str(validated["filename"]),
        mime_type=str(validated["mime_type"]),
        size_bytes=_validated_non_negative_int(validated, "size_bytes"),
        preview_type=str(validated["preview_type"]),
        attachment_revision=_validated_non_negative_int(validated, "attachment_revision"),
        created_at_ms=_validated_epoch_ms(validated, "created_at_ms"),
        message_created_at_ms=message_created_at_ms,
    )


def _extract_knowledge_reference(
    part: JSONDict,
    *,
    message_created_at_ms: int,
) -> KnowledgeAttachmentReference:
    validated = validate_soai_knowledge_content_part(part)
    return KnowledgeAttachmentReference(
        knowledge_attachment_id=str(validated["knowledge_attachment_id"]),
        summary_id=str(validated["summary_id"]),
        source_type=str(validated["source_type"]),
        operation_type=str(validated["operation_type"]),
        title=str(validated["title"]),
        total_count=_validated_non_negative_int(validated, "total_count"),
        visible_count=_validated_non_negative_int(validated, "visible_count"),
        hidden_count=_validated_non_negative_int(validated, "hidden_count"),
        status_counts=_validated_status_counts(validated),
        attachment_revision=_validated_non_negative_int(validated, "attachment_revision"),
        first_event_id=_validated_optional_non_negative_int(validated, "first_event_id"),
        last_event_id=_validated_optional_non_negative_int(validated, "last_event_id"),
        created_at_ms=_validated_epoch_ms(validated, "created_at_ms"),
        finalized_at_ms=_validated_epoch_ms(validated, "finalized_at_ms"),
        message_created_at_ms=message_created_at_ms,
    )


def _message_timestamp(message: JSONDict) -> int:
    return require_unix_epoch_ms(
        message.get("timestamp"),
        error_message="Message timestamp must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )


def _extract_from_content(
    content: JSONValue,
    *,
    message_created_at_ms: int,
    references: ConversationAttachmentReferences,
) -> None:
    if not isinstance(content, list):
        return
    for entry in content:
        part = coerce_json_dict(entry)
        if part is None:
            continue
        part_type = part.get("type")
        if part_type == "soai_file":
            references.files.append(
                _extract_file_reference(part, message_created_at_ms=message_created_at_ms),
            )
        elif part_type == "soai_knowledge":
            references.knowledge.append(
                _extract_knowledge_reference(part, message_created_at_ms=message_created_at_ms),
            )


def extract_message_attachment_references(
    messages: list[JSONDict],
) -> ConversationAttachmentReferences:
    references = ConversationAttachmentReferences()
    for message in messages:
        if message.get("role") != "user":
            continue
        _extract_from_content(
            message.get("content"),
            message_created_at_ms=_message_timestamp(message),
            references=references,
        )
    return references


def extract_content_attachment_references(
    content: list[JSONValue],
    *,
    message_created_at_ms: int,
) -> ConversationAttachmentReferences:
    references = ConversationAttachmentReferences()
    _extract_from_content(
        content,
        message_created_at_ms=message_created_at_ms,
        references=references,
    )
    return references
