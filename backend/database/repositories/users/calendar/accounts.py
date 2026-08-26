"""SoAI - Calendar account repository operations [backend/database/repositories/users/calendar/accounts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.users.account_identifier_validation import (
    optional_linked_mail_account_id,
    require_calendar_account_id,
)
from core.users.account_identifiers import CALENDAR_ACCOUNT_ID_PREFIX
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue
from database.repositories.users.account_sync_field_mappings import (
    build_account_sync_field_mappings,
)
from database.repositories.users.account_validation import (
    optional_json_object,
    require_text,
    require_user_id,
)
from database.repositories.users.domain_account_payload_mapping import (
    AccountPayloadFieldMapping,
    AccountPayloadInsertSpec,
    build_account_payload_insert_spec,
    build_account_payload_updates,
    insert_account_payload_row,
)
from database.repositories.users.domain_account_storage import (
    delete_user_account_row,
    read_user_account_row,
    read_user_account_rows,
    update_user_account_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_calendar_account",
    "read_calendar_accounts",
    "sync_create_calendar_account",
    "sync_delete_calendar_account",
    "sync_update_calendar_account",
)


def _require_caldav_base_url(value: JSONValue) -> SQLiteValue:
    return require_text(value, "caldav_base_url")


_ALLOWED_ACCOUNT_UPDATE_COLUMNS: frozenset[str] = frozenset(
    {
        "caldav_base_url",
        "discovered_principal_json",
        "linked_mail_account_id",
        "last_sync_at_ms",
        "last_sync_error",
        "last_modified_at_ms",
    },
)


def _account_field_mappings() -> tuple[AccountPayloadFieldMapping, ...]:
    return (
        AccountPayloadFieldMapping(
            "caldav_base_url",
            "caldav_base_url",
            _require_caldav_base_url,
        ),
        AccountPayloadFieldMapping(
            "discovered_principal",
            "discovered_principal_json",
            optional_json_object,
        ),
        AccountPayloadFieldMapping(
            "linked_mail_account_id",
            "linked_mail_account_id",
            optional_linked_mail_account_id,
        ),
        *build_account_sync_field_mappings(),
    )


def _account_insert_spec() -> AccountPayloadInsertSpec:
    return build_account_payload_insert_spec(
        table="calendar_accounts",
        account_id_prefix=CALENDAR_ACCOUNT_ID_PREFIX,
        field_mappings=_account_field_mappings(),
        domain_columns=(
            "caldav_base_url",
            "discovered_principal_json",
            "linked_mail_account_id",
        ),
        create_error_message="Failed to create calendar account.",
        created_read_error_message="Failed to read created calendar account.",
    )


async def read_calendar_accounts(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> list[SQLiteRowDict]:
    return await read_user_account_rows(
        database,
        table="calendar_accounts",
        user_id=user_id,
        require_user_id=require_user_id,
    )


async def read_calendar_account(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
) -> SQLiteRowDict | None:
    return await read_user_account_row(
        database,
        table="calendar_accounts",
        user_id=user_id,
        account_id=account_id,
        require_user_id=require_user_id,
        require_account_id=require_calendar_account_id,
    )


def sync_create_calendar_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    external_account_id: str,
    payload: JSONDict,
) -> SQLiteRowDict:
    return insert_account_payload_row(
        conn,
        _account_insert_spec(),
        user_id,
        external_account_id,
        payload,
    )


def sync_update_calendar_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    account_id: str,
    updates: JSONDict,
) -> SQLiteRowDict | None:
    return update_user_account_row(
        conn,
        table="calendar_accounts",
        user_id=user_id,
        account_id=account_id,
        updates=build_account_payload_updates(updates, _account_field_mappings()),
        allowed_columns=_ALLOWED_ACCOUNT_UPDATE_COLUMNS,
        require_user_id=require_user_id,
        require_account_id=require_calendar_account_id,
    )


def sync_delete_calendar_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    account_id: str,
) -> bool:
    return delete_user_account_row(
        conn,
        table="calendar_accounts",
        user_id=user_id,
        account_id=account_id,
        require_user_id=require_user_id,
        require_account_id=require_calendar_account_id,
    )
