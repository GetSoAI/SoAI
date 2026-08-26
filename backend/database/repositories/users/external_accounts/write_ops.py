"""SoAI - External account repository write operations [backend/database/repositories/users/external_accounts/write_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.external_accounts.field_names import (
    EXTERNAL_ACCOUNT_INSERT_COLUMN_NAMES,
    EXTERNAL_ACCOUNT_UPDATE_COLUMN_NAMES,
)
from core.users.account_identifier_validation import require_external_account_id
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.domain_account_storage import (
    delete_user_account_row,
    insert_user_account_row,
    update_user_account_row,
)
from database.repositories.users.external_accounts.row_builders import (
    build_external_account_insert_row,
    build_external_account_update_row,
)
from database.repositories.users.external_accounts.validation import require_user_id

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.types.json import JSONDict

__all__ = (
    "sync_create_external_account",
    "sync_delete_external_account",
    "sync_update_external_account",
)


def sync_create_external_account(
    conn: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
    *,
    user_id: int,
    payload: JSONDict,
) -> SQLiteRowDict:
    normalized_user_id = require_user_id(user_id)
    row = build_external_account_insert_row(
        fernet=fernet,
        user_id=normalized_user_id,
        payload=payload,
    )
    return insert_user_account_row(
        conn,
        table="external_accounts",
        row=row,
        columns=EXTERNAL_ACCOUNT_INSERT_COLUMN_NAMES,
        create_error_message="Failed to create external account.",
        created_read_error_message="Failed to read created external account.",
    )


def sync_update_external_account(
    conn: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
    *,
    user_id: int,
    external_account_id: str,
    updates: JSONDict,
) -> SQLiteRowDict | None:
    normalized_user_id = require_user_id(user_id)
    normalized_account_id = require_external_account_id(external_account_id)
    update_row = build_external_account_update_row(fernet=fernet, updates=updates)
    if not update_row:
        raise ValidationError("updates must not be empty.")
    return update_user_account_row(
        conn,
        table="external_accounts",
        user_id=normalized_user_id,
        account_id=normalized_account_id,
        updates=update_row,
        allowed_columns=EXTERNAL_ACCOUNT_UPDATE_COLUMN_NAMES,
        require_user_id=require_user_id,
        require_account_id=require_external_account_id,
        update_error_message="Failed to update external account.",
    )


def sync_delete_external_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    external_account_id: str,
) -> bool:
    return delete_user_account_row(
        conn,
        table="external_accounts",
        user_id=user_id,
        account_id=external_account_id,
        require_user_id=require_user_id,
        require_account_id=require_external_account_id,
    )
