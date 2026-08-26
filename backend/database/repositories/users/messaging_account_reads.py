"""SoAI - Owner-scoped Messaging account reads [backend/database/repositories/users/messaging_account_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from core.messaging.account_models import MessagingConversationVersion
from core.security.secret_crypto import decrypt_required_secret
from core.serialization.json_parsing import parse_json_dict
from core.users.user_id import require_strict_user_id
from database.core.query_execution import query_one_to_dict, query_to_dicts, sync_fetch_one_as_dict
from database.core.row_fields import require_row_epoch_ms, require_row_non_empty_str
from database.repositories.users.messaging_account_rows import format_messaging_account_row

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "MESSAGING_ACCOUNT_READ_SQL",
    "read_messaging_account",
    "read_messaging_account_credentials",
    "read_messaging_accounts",
    "read_messaging_bound_conversation_versions",
    "read_messaging_transport_account",
    "read_enabled_messaging_transport_accounts",
    "read_deleting_messaging_transport_accounts",
    "read_reconcilable_messaging_transport_accounts",
    "sync_read_messaging_account",
)

MESSAGING_ACCOUNT_READ_SQL = """
SELECT a.*,
    COALESCE(
        (
            SELECT json_group_array(json(sender_record))
            FROM (
                SELECT json_object(
                    'sender_id', sender.sender_id,
                    'display_label', sender.display_label
                ) AS sender_record
                FROM messaging_authorized_senders AS sender
                WHERE sender.account_id = a.account_id
                  AND sender.user_id = a.user_id
                ORDER BY sender.sender_id
            )
        ),
        json('[]')
    ) AS authorized_senders_json
FROM messaging_accounts AS a
"""


def sync_read_messaging_account(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"{MESSAGING_ACCOUNT_READ_SQL} WHERE a.user_id = ? AND a.account_id = ?",
            (user_id, account_id),
        ),
    )
    return format_messaging_account_row(row)


async def read_messaging_accounts(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        f"{MESSAGING_ACCOUNT_READ_SQL} WHERE a.user_id = ? ORDER BY a.updated_at_ms DESC, a.account_id",
        (require_strict_user_id(user_id),),
    )
    return [account for row in rows if (account := format_messaging_account_row(row))]


async def read_messaging_account(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        f"{MESSAGING_ACCOUNT_READ_SQL} WHERE a.user_id = ? AND a.account_id = ?",
        (require_strict_user_id(user_id), account_id),
    )
    return format_messaging_account_row(row)


async def read_messaging_account_credentials(
    database: aiosqlite.Connection,
    *,
    fernets: tuple[Fernet, ...],
    user_id: int,
    account_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        "SELECT credential_ciphertext FROM messaging_accounts WHERE user_id = ? AND account_id = ?",
        (require_strict_user_id(user_id), account_id),
    )
    if row is None:
        return None
    encrypted_value = row.get("credential_ciphertext")
    encrypted = encrypted_value if isinstance(encrypted_value, str) else None
    plaintext = decrypt_required_secret(
        fernets,
        encrypted,
        label="Messaging account credentials",
    )
    return parse_json_dict(plaintext, field="Messaging account credentials")


def _transport_account_from_row(
    row: SQLiteRowDict | None,
    *,
    fernets: tuple[Fernet, ...],
) -> JSONDict | None:
    if row is None:
        return None
    account = format_messaging_account_row(row)
    if account is None:
        return None
    encrypted_value = row.get("credential_ciphertext")
    encrypted = encrypted_value if isinstance(encrypted_value, str) else None
    plaintext = decrypt_required_secret(
        fernets,
        encrypted,
        label="Messaging account credentials",
    )
    account["credentials"] = parse_json_dict(
        plaintext,
        field="Messaging account credentials",
    )
    account["credential_fingerprint"] = require_row_non_empty_str(
        row.get("credential_fingerprint"),
        label="Messaging account credential fingerprint",
        build_error=StateError,
    )
    return account


async def read_messaging_transport_account(
    database: aiosqlite.Connection,
    *,
    fernets: tuple[Fernet, ...],
    account_id: str,
    platform: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        f"{MESSAGING_ACCOUNT_READ_SQL} WHERE a.account_id = ? AND a.platform = ?",
        (account_id, platform),
    )
    return _transport_account_from_row(row, fernets=fernets)


async def read_enabled_messaging_transport_accounts(
    database: aiosqlite.Connection,
    *,
    fernets: tuple[Fernet, ...],
    platform: str,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        f"""
        {MESSAGING_ACCOUNT_READ_SQL}
        WHERE a.platform = ? AND a.lifecycle_state IN ('enabled', 'degraded')
        ORDER BY a.account_id
        """,
        (platform,),
    )
    accounts: list[JSONDict] = []
    for row in rows:
        account = _transport_account_from_row(row, fernets=fernets)
        if account is not None:
            accounts.append(account)
    return accounts


async def read_deleting_messaging_transport_accounts(
    database: aiosqlite.Connection,
    *,
    fernets: tuple[Fernet, ...],
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        f"""
        {MESSAGING_ACCOUNT_READ_SQL}
        WHERE a.lifecycle_state = 'deleting'
        ORDER BY a.account_id
        """,
    )
    accounts: list[JSONDict] = []
    for row in rows:
        account = _transport_account_from_row(row, fernets=fernets)
        if account is not None:
            accounts.append(account)
    return accounts


async def read_reconcilable_messaging_transport_accounts(
    database: aiosqlite.Connection,
    *,
    fernets: tuple[Fernet, ...],
    platform: str,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        f"""
        {MESSAGING_ACCOUNT_READ_SQL}
        WHERE a.platform = ? AND a.lifecycle_state != 'deleting'
          AND (a.lifecycle_state IN ('enabled', 'degraded') OR a.health_code IS NOT NULL)
        ORDER BY a.account_id
        """,
        (platform,),
    )
    accounts: list[JSONDict] = []
    for row in rows:
        account = _transport_account_from_row(row, fernets=fernets)
        if account is not None:
            accounts.append(account)
    return accounts


async def read_messaging_bound_conversation_versions(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
) -> tuple[MessagingConversationVersion, ...]:
    rows = await query_to_dicts(
        database,
        """
        SELECT conversation.id AS conv_id, conversation.last_modified_at_ms
        FROM messaging_thread_bindings AS binding
        JOIN webui_conversations AS conversation
          ON conversation.id = binding.conv_id AND conversation.user_id = binding.user_id
        WHERE binding.account_id = ? AND binding.user_id = ?
        ORDER BY conversation.id
        """,
        (account_id, require_strict_user_id(user_id)),
    )
    return tuple(
        MessagingConversationVersion(
            conv_id=require_row_non_empty_str(
                row.get("conv_id"),
                label="Messaging conversation id",
                build_error=StateError,
            ),
            last_modified_at_ms=require_row_epoch_ms(
                row.get("last_modified_at_ms"),
                label="Messaging conversation modified time",
                build_error=StateError,
            ),
        )
        for row in rows
    )
