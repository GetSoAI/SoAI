"""SoAI - MCP access token repository write operations [backend/database/repositories/users/mcp_access_tokens/write_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.database.requests import InsertMcpAccessTokenRequest
from core.errors.exceptions import StateError
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.mcp_access_token_row_normalization import (
    normalize_mcp_access_token_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_insert_token",
    "sync_record_last_used",
    "sync_revoke_token",
)


def sync_get_token_by_id(
    conn: sqlite3.Connection,
    token_id: str,
    *,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    cursor = conn.execute(
        """
        SELECT tokens.* FROM mcp_access_tokens tokens
        JOIN webui_users users ON users.id = tokens.user_id
        WHERE tokens.token_id = ? AND users.account_type = 'human'
        """,
        (token_id,),
    )
    row = sync_fetch_one_as_dict(cursor)
    return normalize_mcp_access_token_row(row, decrypt_hash=decrypt_hash)


def sync_insert_token(
    conn: sqlite3.Connection,
    request: InsertMcpAccessTokenRequest,
    encrypt_hash: Callable[[str], str],
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict:
    inserted = conn.execute(
        """
        INSERT INTO mcp_access_tokens (
            token_id,
            user_id,
            hashed_token_ciphertext,
            salt,
            fingerprint,
            label,
            prefix,
            created_at_ms,
            last_used_at_ms,
            expires_at_ms,
            revoked,
            revoked_at_ms,
            revoked_by,
            encryption_version
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, NULL, NULL, ?
        WHERE EXISTS (
            SELECT 1 FROM webui_users
            WHERE id = ? AND account_type = 'human'
        )
        """,
        (
            request.token_id,
            int(request.user_id),
            encrypt_hash(request.hashed_token),
            request.salt,
            request.fingerprint,
            request.label,
            request.prefix,
            int(request.created_at_ms),
            request.expires_at_ms,
            int(request.encryption_version),
            int(request.user_id),
        ),
    ).rowcount
    if inserted != 1:
        raise StateError("MCP access token owner must be a human account.")
    record = sync_get_token_by_id(conn, request.token_id, decrypt_hash=decrypt_hash)
    if record is None:
        raise StateError("MCP access token not found after INSERT.")
    return record


def sync_record_last_used(conn: sqlite3.Connection, token_id: str, now_ms: int) -> None:
    conn.execute(
        "UPDATE mcp_access_tokens SET last_used_at_ms = ? WHERE token_id = ?",
        (int(now_ms), token_id),
    )


def sync_revoke_token(
    conn: sqlite3.Connection,
    token_id: str,
    revoked_by: int | None,
    now_ms: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    existing = sync_get_token_by_id(conn, token_id, decrypt_hash=decrypt_hash)
    if existing is None:
        return None
    if existing.get("revoked") is True:
        return existing
    updated = conn.execute(
        """
        UPDATE mcp_access_tokens
        SET revoked = 1, revoked_at_ms = ?, revoked_by = ?
        WHERE token_id = ? AND revoked = 0
        """,
        (int(now_ms), revoked_by, token_id),
    ).rowcount
    if not updated:
        return sync_get_token_by_id(conn, token_id, decrypt_hash=decrypt_hash)
    return sync_get_token_by_id(conn, token_id, decrypt_hash=decrypt_hash)
