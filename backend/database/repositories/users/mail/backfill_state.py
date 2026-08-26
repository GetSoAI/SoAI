"""SoAI - Mail folder backfill state repository operations [backend/database/repositories/users/mail/backfill_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.users.account_identifier_validation import require_mail_folder_id
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.sql_builders import build_upsert_statement
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import (
    optional_epoch_ms,
    require_user_id,
)

__all__ = (
    "read_mail_backfill_state",
    "sync_update_mail_backfill_state",
)


async def read_mail_backfill_state(
    database: aiosqlite.Connection,
    /,
    user_id: int,
    folder_id: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        """
        SELECT state.*
        FROM mail_folder_backfill_state AS state
        INNER JOIN mail_folders AS folder ON folder.id = state.folder_id
        WHERE folder.user_id = ? AND state.folder_id = ?
        LIMIT 1
        """,
        (require_user_id(user_id), require_mail_folder_id(folder_id)),
    )


def sync_update_mail_backfill_state(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    folder_id: str,
    checkpoint_json: str | None,
    last_backfill_at_ms: int | None,
) -> bool:
    existing = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT id FROM mail_folders WHERE user_id = ? AND id = ? LIMIT 1",
            (require_user_id(user_id), require_mail_folder_id(folder_id)),
        ),
    )
    if existing is None:
        return False
    conn.execute(
        build_upsert_statement(
            table="mail_folder_backfill_state",
            columns=("folder_id", "checkpoint_json", "last_backfill_at_ms"),
            conflict_columns=("folder_id",),
            update_columns=("checkpoint_json", "last_backfill_at_ms"),
        ),
        (
            require_mail_folder_id(folder_id),
            coerce_optional_trimmed_str(checkpoint_json),
            optional_epoch_ms(last_backfill_at_ms),
        ),
    )
    return True
