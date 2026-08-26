"""SoAI - WebUI attachment event payload builders [backend/core/attachments/attachment_event_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_conversation import (
    ConversationAttachmentChangedEvent,
    KnowledgeAttachmentChangedEvent,
)
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "conversation_attachment_changed_event",
    "knowledge_attachment_changed_event",
)


def _require_int(payload: JSONDict, field_name: str) -> int:
    value = payload.get(field_name)
    if not is_strict_int(value):
        raise StateError(f"Attachment event field {field_name} is invalid.")
    return value


def _require_str(payload: JSONDict, field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"Attachment event field {field_name} is invalid.")
    return value


def _optional_str(payload: JSONDict, field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StateError(f"Attachment event field {field_name} is invalid.")
    return value


def _attachment_event_payload(attachment: JSONDict) -> JSONDict:
    payload = dict(attachment)
    payload.pop("provider_text", None)
    return payload


def conversation_attachment_changed_event(
    attachment: JSONDict,
) -> ConversationAttachmentChangedEvent:
    return ConversationAttachmentChangedEvent(
        user_id=_require_int(attachment, "user_id"),
        conv_id=_require_str(attachment, "conv_id"),
        attachment_id=_require_str(attachment, "attachment_id"),
        client_attachment_id=_optional_str(attachment, "client_attachment_id"),
        parse_state=_require_str(attachment, "parse_state"),
        state=_require_str(attachment, "state"),
        attachment_revision=_require_int(attachment, "attachment_revision"),
        updated_at_ms=_require_int(attachment, "updated_at_ms"),
        attachment=_attachment_event_payload(attachment),
    )


def knowledge_attachment_changed_event(summary: JSONDict) -> KnowledgeAttachmentChangedEvent:
    return KnowledgeAttachmentChangedEvent(
        user_id=_require_int(summary, "user_id"),
        conv_id=_require_str(summary, "conv_id"),
        knowledge_attachment_id=_require_str(summary, "knowledge_attachment_id"),
        task_id=_optional_str(summary, "task_id"),
        processing_state=_require_str(summary, "processing_state"),
        state=_require_str(summary, "state"),
        attachment_revision=_require_int(summary, "attachment_revision"),
        updated_at_ms=_require_int(summary, "updated_at_ms"),
        summary=summary,
    )
