"""SoAI - Password vault write operations (encryption and scope enforcement) [backend/database/repositories/users/password_vault_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError, ValidationError
from core.timing.epoch import epoch_ms
from core.users.user_id import is_strict_user_id
from core.web.site_scope import SiteScope, assert_url_allowed
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.password_vault_crypto import (
    decrypt_optional,
    decrypt_required,
    encrypt_optional,
    encrypt_required,
    mask_username,
)
from database.repositories.users.password_vault_label_normalization import (
    normalize_password_vault_label,
)
from database.repositories.users.password_vault_reads import DatabasePasswordVaultReads
from database.repositories.users.password_vault_scope_json import (
    parse_password_vault_scope_json,
    serialize_password_vault_scope_json,
)

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabasePasswordVault", "sync_create_password_vault_credential")


def sync_create_password_vault_credential(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    credential_id: str,
    user_id: int,
    label: str,
    scope: SiteScope,
    username_plaintext: str | None,
    password_plaintext: str,
) -> str:
    if not is_strict_user_id(user_id):
        raise ValidationError("Password vault user_id must be positive.")
    normalized_label = normalize_password_vault_label(label)
    scope_json = serialize_password_vault_scope_json(scope)
    username_hint = mask_username(username_plaintext)
    username_encrypted = encrypt_optional(fernets, username_plaintext)
    password_encrypted = encrypt_required(fernets, password_plaintext)
    normalized_credential_id = credential_id.strip()
    if not normalized_credential_id:
        raise ValidationError("Password vault credential_id must not be empty.")
    now = epoch_ms()
    try:
        conn.execute(
            """
            INSERT INTO webui_password_vault_credentials
                (id, user_id, label, scope_json, username_hint, username_encrypted, password_encrypted, created_at_ms, last_used_at_ms)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                normalized_credential_id,
                user_id,
                normalized_label,
                scope_json,
                username_hint,
                username_encrypted,
                password_encrypted,
                now,
            ),
        )
        return normalized_credential_id
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in ("unique", "primary_key"):
            raise ValidationError(
                "Password vault credential label must be unique per user.",
            ) from exception
        if constraint_type in ("check", "not_null"):
            raise ValidationError(
                f"Invalid password vault credential: constraint violation on {detail or 'unknown field'}.",
            ) from exception
        raise StateError(f"Database constraint violation: {exception}") from exception


def _sync_delete_all_credentials(conn: sqlite3.Connection, user_id: int) -> int:
    if not is_strict_user_id(user_id):
        raise ValidationError("Password vault user_id must be positive.")
    cursor = conn.execute(
        "DELETE FROM webui_password_vault_credentials WHERE user_id = ?",
        (user_id,),
    )
    if cursor.rowcount is None or cursor.rowcount < 0:
        return 0
    return int(cursor.rowcount)


def _sync_delete_credential(conn: sqlite3.Connection, user_id: int, credential_id: str) -> bool:
    if not is_strict_user_id(user_id):
        raise ValidationError("Password vault user_id must be positive.")
    normalized_id = credential_id.strip()
    if not normalized_id:
        raise ValidationError("Password vault credential_id must not be empty.")
    cursor = conn.execute(
        "DELETE FROM webui_password_vault_credentials WHERE id = ? AND user_id = ?",
        (normalized_id, user_id),
    )
    return bool(cursor.rowcount and cursor.rowcount > 0)


def _sync_update_last_used(
    conn: sqlite3.Connection,
    user_id: int,
    credential_id: str,
    last_used_at_ms: int,
) -> None:
    if not is_strict_user_id(user_id):
        raise ValidationError("Password vault user_id must be positive.")
    normalized_id = credential_id.strip()
    if not normalized_id:
        raise ValidationError("Password vault credential_id must not be empty.")
    if last_used_at_ms <= 0:
        raise ValidationError("Password vault last_used_at_ms must be positive.")
    conn.execute(
        "UPDATE webui_password_vault_credentials SET last_used_at_ms = ? WHERE id = ? AND user_id = ?",
        (last_used_at_ms, normalized_id, user_id),
    )


def _sync_get_credential_plaintext_for_url(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    user_id: int,
    credential_id: str,
    current_page_url: str,
) -> tuple[SiteScope, str | None, str]:
    if not is_strict_user_id(user_id):
        raise ValidationError("Password vault user_id must be positive.")
    normalized_id = credential_id.strip()
    if not normalized_id:
        raise ValidationError("Password vault credential_id must not be empty.")
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT scope_json, username_encrypted, password_encrypted
            FROM webui_password_vault_credentials
            WHERE id = ? AND user_id = ?
            """,
            (normalized_id, user_id),
        ),
    )
    if row is None:
        raise ValidationError("Password vault credential was not found.")
    scope_raw = row.get("scope_json")
    username_encrypted = row.get("username_encrypted")
    password_encrypted = row.get("password_encrypted")
    if not isinstance(scope_raw, str) or not scope_raw.strip():
        raise StateError("Password vault credential row is missing scope_json.")
    scope = parse_password_vault_scope_json(scope_raw)
    try:
        assert_url_allowed(current_page_url, scope)
    except ValueError as exception:
        raise ValidationError(
            "Password vault credential is not allowed for the current page URL.",
        ) from exception
    username_plaintext = decrypt_optional(
        fernets,
        str(username_encrypted) if username_encrypted else None,
    )
    password_plaintext = decrypt_required(
        fernets,
        str(password_encrypted) if password_encrypted else None,
    )
    return (scope, username_plaintext, password_plaintext)


class DatabasePasswordVault(DatabasePasswordVaultReads):
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        super().__init__(deps)
        self.fernets = deps.fernet

    async def delete_credential(self, user_id: int, credential_id: str) -> bool:
        return bool(
            await self.core.writer.queue_write_operation(
                _sync_delete_credential,
                user_id,
                credential_id,
            ),
        )

    async def delete_all_credentials(self, user_id: int) -> int:
        deleted_count = await self.core.writer.queue_write_operation(
            _sync_delete_all_credentials,
            user_id,
        )
        if not isinstance(deleted_count, int):
            raise StateError("Password vault delete-all did not return an integer count.")
        return deleted_count

    async def update_last_used(
        self,
        user_id: int,
        credential_id: str,
        last_used_at_ms: int,
    ) -> None:
        await self.core.writer.queue_write_operation(
            _sync_update_last_used,
            user_id,
            credential_id,
            last_used_at_ms,
        )

    async def get_credential_plaintext_for_url(
        self,
        user_id: int,
        credential_id: str,
        current_page_url: str,
    ) -> tuple[SiteScope, str | None, str]:
        return await self.core.writer.queue_write_operation(
            _sync_get_credential_plaintext_for_url,
            self.fernets,
            user_id,
            credential_id,
            current_page_url,
        )
