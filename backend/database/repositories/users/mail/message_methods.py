"""SoAI - Mail repository message methods [backend/database/repositories/users/mail/message_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.core.flags import FEATURE_AUTH
from database.repositories.users.mail.message_body_writes import (
    sync_replace_mail_message_body,
)
from database.repositories.users.mail.message_reads import (
    read_mail_attachment_part,
    read_mail_message,
    read_mail_message_body,
    read_mail_message_parts,
    read_mail_messages,
)
from database.repositories.users.mail.message_writes import (
    sync_delete_mail_message,
    sync_delete_mail_messages,
    sync_update_mail_message,
    sync_upsert_mail_message,
)
from database.repositories.users.mail.record_normalization import (
    normalize_mail_body_row,
    normalize_mail_message_row,
    normalize_mail_part_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.users.mail.internal_protocols import (
        DatabaseMailCoreOwnerProtocol,
    )

__all__ = (
    "delete_message_method",
    "delete_messages_method",
    "get_attachment_part_method",
    "get_message_method",
    "list_messages_method",
    "replace_message_body_method",
    "update_message_method",
    "upsert_message_method",
)


async def upsert_message_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
    folder_id: str,
    payload: JSONDict,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_upsert_mail_message,
        user_id,
        account_id,
        folder_id,
        payload,
    )
    normalized = normalize_mail_message_row(row)
    if normalized is None:
        raise StateError("Mail message is invalid.")
    return normalized


async def list_messages_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    folder_id: str,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    rows = await self.core.reader.execute_read(
        read_mail_messages,
        user_id=user_id,
        folder_id=folder_id,
    )
    return [normalized for row in rows if (normalized := normalize_mail_message_row(row))]


async def get_message_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    message_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.reader.execute_read(
        read_mail_message,
        user_id=user_id,
        message_id=message_id,
    )
    normalized = normalize_mail_message_row(row)
    if normalized is None:
        return None
    body_row = await self.core.reader.execute_read(
        read_mail_message_body,
        user_id=user_id,
        message_id=message_id,
    )
    part_rows = await self.core.reader.execute_read(
        read_mail_message_parts,
        user_id=user_id,
        message_id=message_id,
    )
    normalized["body"] = normalize_mail_body_row(body_row)
    normalized["parts"] = [
        item for row_value in part_rows if (item := normalize_mail_part_row(row_value))
    ]
    return normalized


async def get_attachment_part_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    attachment_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.reader.execute_read(
        read_mail_attachment_part,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    return normalize_mail_part_row(row)


async def replace_message_body_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    message_id: str,
    body_text: str,
    body_html: str | None,
    total_chars: int,
    parts: list[JSONDict],
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_replace_mail_message_body,
        user_id,
        message_id,
        body_text,
        body_html,
        total_chars,
        parts,
    )
    return normalize_mail_body_row(row)


async def update_message_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    message_id: str,
    updates: JSONDict,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_update_mail_message,
        user_id,
        message_id,
        updates,
    )
    return normalize_mail_message_row(row)


async def delete_message_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    message_id: str,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return bool(
        await self.core.writer.queue_write_operation(
            sync_delete_mail_message,
            user_id,
            message_id,
        ),
    )


async def delete_messages_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    folder_id: str,
    message_ids: list[str],
) -> int:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return int(
        await self.core.writer.queue_write_operation(
            sync_delete_mail_messages,
            user_id,
            folder_id,
            message_ids,
        ),
    )
