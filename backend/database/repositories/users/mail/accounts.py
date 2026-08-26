"""SoAI - Mail account repository operations [backend/database/repositories/users/mail/accounts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.users.account_identifier_validation import (
    require_mail_account_id,
)
from core.users.account_identifiers import MAIL_ACCOUNT_ID_PREFIX
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue
from database.repositories.users.account_sync_field_mappings import (
    build_account_sync_field_mappings,
)
from database.repositories.users.account_validation import (
    optional_json_object,
    require_port,
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
from database.repositories.users.mail.validation import (
    require_protocol,
    require_security,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_mail_account",
    "read_mail_accounts",
    "sync_create_mail_account",
    "sync_delete_mail_account",
    "sync_update_mail_account",
)


def _require_inbound_host(value: JSONValue) -> SQLiteValue:
    return require_text(value, "inbound_host")


def _require_inbound_port(value: JSONValue) -> SQLiteValue:
    return require_port(value, "inbound_port")


def _require_inbound_security(value: JSONValue) -> SQLiteValue:
    return require_security(value, "inbound_security")


def _require_smtp_host(value: JSONValue) -> SQLiteValue:
    return require_text(value, "smtp_host")


def _require_smtp_port(value: JSONValue) -> SQLiteValue:
    return require_port(value, "smtp_port")


def _require_smtp_security(value: JSONValue) -> SQLiteValue:
    return require_security(value, "smtp_security")


_ALLOWED_ACCOUNT_UPDATE_COLUMNS: frozenset[str] = frozenset(
    {
        "protocol",
        "inbound_host",
        "inbound_port",
        "inbound_security",
        "smtp_host",
        "smtp_port",
        "smtp_security",
        "folder_mapping_json",
        "last_sync_at_ms",
        "last_sync_error",
        "last_modified_at_ms",
    },
)


def _account_field_mappings() -> tuple[AccountPayloadFieldMapping, ...]:
    return (
        AccountPayloadFieldMapping("protocol", "protocol", require_protocol),
        AccountPayloadFieldMapping("inbound_host", "inbound_host", _require_inbound_host),
        AccountPayloadFieldMapping("inbound_port", "inbound_port", _require_inbound_port),
        AccountPayloadFieldMapping(
            "inbound_security",
            "inbound_security",
            _require_inbound_security,
        ),
        AccountPayloadFieldMapping("smtp_host", "smtp_host", _require_smtp_host),
        AccountPayloadFieldMapping("smtp_port", "smtp_port", _require_smtp_port),
        AccountPayloadFieldMapping(
            "smtp_security",
            "smtp_security",
            _require_smtp_security,
        ),
        AccountPayloadFieldMapping(
            "folder_mapping",
            "folder_mapping_json",
            optional_json_object,
        ),
        *build_account_sync_field_mappings(),
    )


def _account_insert_spec() -> AccountPayloadInsertSpec:
    return build_account_payload_insert_spec(
        table="mail_accounts",
        account_id_prefix=MAIL_ACCOUNT_ID_PREFIX,
        field_mappings=_account_field_mappings(),
        domain_columns=(
            "protocol",
            "inbound_host",
            "inbound_port",
            "inbound_security",
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "folder_mapping_json",
        ),
        create_error_message="Failed to create mail account.",
        created_read_error_message="Failed to read created mail account.",
    )


async def read_mail_accounts(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> list[SQLiteRowDict]:
    return await read_user_account_rows(
        database,
        table="mail_accounts",
        user_id=user_id,
        require_user_id=require_user_id,
    )


async def read_mail_account(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
) -> SQLiteRowDict | None:
    return await read_user_account_row(
        database,
        table="mail_accounts",
        user_id=user_id,
        account_id=account_id,
        require_user_id=require_user_id,
        require_account_id=require_mail_account_id,
    )


def sync_update_mail_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    account_id: str,
    updates: JSONDict,
) -> SQLiteRowDict | None:
    account_updates = build_account_payload_updates(updates, _account_field_mappings())
    return update_user_account_row(
        conn,
        table="mail_accounts",
        user_id=user_id,
        account_id=account_id,
        updates=account_updates,
        allowed_columns=_ALLOWED_ACCOUNT_UPDATE_COLUMNS,
        require_account_id=require_mail_account_id,
        require_user_id=require_user_id,
    )


def sync_create_mail_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    external_account_id: str,
    payload: JSONDict,
) -> SQLiteRowDict:
    return insert_account_payload_row(
        conn,
        _account_insert_spec(),
        user_id=user_id,
        external_account_id=external_account_id,
        payload=payload,
    )


def sync_delete_mail_account(conn: sqlite3.Connection, *, user_id: int, account_id: str) -> bool:
    account_table = "mail_accounts"
    return delete_user_account_row(
        conn,
        account_id=account_id,
        user_id=user_id,
        table=account_table,
        require_account_id=require_mail_account_id,
        require_user_id=require_user_id,
    )
