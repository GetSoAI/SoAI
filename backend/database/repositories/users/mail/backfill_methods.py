"""SoAI - Mail repository backfill methods [backend/database/repositories/users/mail/backfill_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.flags import FEATURE_AUTH
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.repositories.users.mail.backfill_state import (
    read_mail_backfill_state,
    sync_update_mail_backfill_state,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.users.mail.internal_protocols import (
        DatabaseMailCoreOwnerProtocol,
    )

__all__ = (
    "get_backfill_state_method",
    "update_backfill_state_method",
)


async def get_backfill_state_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    folder_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.reader.execute_read(
        read_mail_backfill_state,
        user_id,
        folder_id,
    )
    if row is None:
        return None
    return sqlite_row_dict_to_json_dict(row)


async def update_backfill_state_method(
    self: DatabaseMailCoreOwnerProtocol,
    *,
    user_id: int,
    folder_id: str,
    checkpoint_json: str | None,
    last_backfill_at_ms: int | None,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return bool(
        await self.core.writer.queue_write_operation(
            sync_update_mail_backfill_state,
            user_id,
            folder_id,
            checkpoint_json,
            last_backfill_at_ms,
        ),
    )
