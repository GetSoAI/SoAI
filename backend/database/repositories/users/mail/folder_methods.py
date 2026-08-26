"""SoAI - Mail repository folder methods [backend/database/repositories/users/mail/folder_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.core.flags import FEATURE_AUTH
from database.repositories.users.mail.folders import (
    read_mail_folder,
    read_mail_folder_by_remote_mailbox,
    read_mail_folders,
    sync_delete_mail_folder,
    sync_upsert_mail_folder,
)
from database.repositories.users.mail.record_normalization import (
    normalize_mail_folder_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.users.mail.internal_protocols import (
        DatabaseMailCoreOwnerProtocol,
    )

__all__ = (
    "delete_folder_method",
    "get_folder_by_remote_mailbox_method",
    "get_folder_method",
    "list_folders_method",
    "upsert_folder_method",
)


async def upsert_folder_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
    payload: JSONDict,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_upsert_mail_folder,
        user_id,
        account_id,
        payload,
    )
    normalized = normalize_mail_folder_row(row)
    if normalized is None:
        raise StateError("Mail folder is invalid.")
    return normalized


async def list_folders_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    rows = await self.core.reader.execute_read(
        read_mail_folders,
        user_id=user_id,
        account_id=account_id,
    )
    return [normalized for row in rows if (normalized := normalize_mail_folder_row(row))]


async def get_folder_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    folder_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.reader.execute_read(
        read_mail_folder,
        user_id=user_id,
        folder_id=folder_id,
    )
    return normalize_mail_folder_row(row)


async def get_folder_by_remote_mailbox_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
    remote_mailbox: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.reader.execute_read(
        read_mail_folder_by_remote_mailbox,
        user_id=user_id,
        account_id=account_id,
        remote_mailbox=remote_mailbox,
    )
    return normalize_mail_folder_row(row)


async def delete_folder_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    folder_id: str,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return bool(
        await self.core.writer.queue_write_operation(
            sync_delete_mail_folder,
            user_id,
            folder_id,
        ),
    )
