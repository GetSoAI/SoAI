"""SoAI - Conversation composer draft content validation [backend/core/conversations/conversation_draft_content_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_content_validation import (
    validate_soai_file_content_part,
)
from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict
from core.workspaces.soai_path_draft_record_validation import (
    validate_soai_path_draft_record,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("CHAT_COMPOSER_TEXT_MAX_LENGTH", "validate_conversation_draft_entries")

CHAT_COMPOSER_TEXT_MAX_LENGTH = 32768


def validate_conversation_draft_entries(value: list[JSONValue]) -> list[JSONValue]:
    validated_entries: list[JSONValue] = []
    for entry in value:
        record = coerce_json_dict(entry)
        if record is None:
            raise ValidationError("Conversation draft attachment_content entries must be objects.")
        entry_type = record.get("type")
        if entry_type == "soai_file":
            validated_entries.append(validate_soai_file_content_part(record))
            continue
        if entry_type == "soai_path_record":
            validated_entries.append(validate_soai_path_draft_record(record))
            continue
        if entry_type == "soai_knowledge":
            raise ValidationError("Conversation drafts do not support knowledge attachments.")
        raise ValidationError("Conversation draft attachment_content entry type is unsupported.")
    return validated_entries
