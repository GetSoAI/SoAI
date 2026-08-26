"""SoAI - WebUI attachment parse failure persistence [backend/core/attachments/attachment_parse_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.attachments.protocols_database import (
        DatabaseConversationAttachmentsProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("mark_attachment_parse_failed",)


async def mark_attachment_parse_failed(
    database_attachments: DatabaseConversationAttachmentsProtocol,
    *,
    conv_id: str,
    user_id: int,
    attachment_id: str,
    parse_error: str,
) -> JSONDict | None:
    now_ms = epoch_ms()
    return await database_attachments.update_attachment_parse_state(
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
        provider_mode=None,
        provider_text=None,
        provider_text_truncated=None,
        parse_state="failed",
        parse_error=parse_error,
        parsed_at_ms=now_ms,
        updated_at_ms=now_ms,
    )
