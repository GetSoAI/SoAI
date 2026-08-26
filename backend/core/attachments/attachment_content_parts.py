"""SoAI - Canonical WebUI attachment content part builders [backend/core/attachments/attachment_content_parts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_content_validation import (
    SOURCE_ATTACHMENT_UNAVAILABLE_REASON,
    validate_soai_file_content_part,
    validate_soai_file_unavailable_content_part,
    validate_soai_knowledge_content_part,
    validate_soai_knowledge_unavailable_content_part,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "content_part_from_file_attachment",
    "content_part_from_unavailable_file",
    "content_part_from_knowledge_summary",
    "content_part_from_unavailable_knowledge",
)


def content_part_from_file_attachment(attachment: JSONDict) -> JSONDict:
    return validate_soai_file_content_part(
        {
            "type": "soai_file",
            "attachment_id": attachment["attachment_id"],
            "file_id": attachment["file_id"],
            "filename": attachment["filename"],
            "mime_type": attachment["mime_type"],
            "size_bytes": attachment["size_bytes"],
            "preview_type": attachment["preview_type"],
            "attachment_revision": attachment["attachment_revision"],
            "created_at_ms": attachment["created_at_ms"],
        },
    )


def content_part_from_knowledge_summary(summary: JSONDict) -> JSONDict:
    return validate_soai_knowledge_content_part(
        {
            "type": "soai_knowledge",
            "knowledge_attachment_id": summary["knowledge_attachment_id"],
            "summary_id": summary["summary_id"],
            "source_type": summary["source_type"],
            "operation_type": summary["operation_type"],
            "title": summary["title"],
            "total_count": summary["total_count"],
            "visible_count": summary["visible_count"],
            "hidden_count": summary["hidden_count"],
            "status_counts": summary["status_counts"],
            "attachment_revision": summary["attachment_revision"],
            "first_event_id": summary["first_event_id"],
            "last_event_id": summary["last_event_id"],
            "created_at_ms": summary["created_at_ms"],
            "finalized_at_ms": summary["finalized_at_ms"],
        },
    )


def content_part_from_unavailable_file(part: JSONDict) -> JSONDict:
    validated = validate_soai_file_content_part(part)
    return validate_soai_file_unavailable_content_part(
        {
            "type": "soai_file_unavailable",
            "filename": validated["filename"],
            "mime_type": validated["mime_type"],
            "size_bytes": validated["size_bytes"],
            "preview_type": validated["preview_type"],
            "reason": SOURCE_ATTACHMENT_UNAVAILABLE_REASON,
        },
    )


def content_part_from_unavailable_knowledge(part: JSONDict) -> JSONDict:
    validated = validate_soai_knowledge_content_part(part)
    return validate_soai_knowledge_unavailable_content_part(
        {
            "type": "soai_knowledge_unavailable",
            "title": validated["title"],
            "source_type": validated["source_type"],
            "reason": SOURCE_ATTACHMENT_UNAVAILABLE_REASON,
        },
    )
