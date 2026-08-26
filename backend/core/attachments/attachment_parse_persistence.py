"""SoAI - WebUI attachment parse outcome persistence [backend/core/attachments/attachment_parse_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.attachments.attachment_parse_classification import AttachmentParseOutcome
    from core.attachments.protocols_database import (
        DatabaseConversationAttachmentsProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("persist_attachment_parse_outcome",)


async def persist_attachment_parse_outcome(
    database_attachments: DatabaseConversationAttachmentsProtocol,
    *,
    conv_id: str,
    user_id: int,
    attachment_id: str,
    outcome: AttachmentParseOutcome,
    now_ms: int,
) -> JSONDict | None:
    return await database_attachments.update_attachment_parse_state(
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
        provider_mode=outcome.provider_mode,
        provider_text=outcome.provider_text,
        provider_text_truncated=outcome.provider_text_truncated,
        parse_state=outcome.parse_state,
        parse_error=outcome.parse_error,
        parsed_at_ms=now_ms,
        updated_at_ms=now_ms,
    )
