"""SoAI - Password vault read operations (no secrets) [backend/database/repositories/users/password_vault_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError, ValidationError
from core.users.user_id import is_strict_user_id
from core.web.site_scope_codec import coerce_site_scope_json_dict
from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import coerce_int_from_sqlite
from database.repositories.users.password_vault_label_normalization import (
    normalize_password_vault_search_query,
)
from database.repositories.users.password_vault_scope_json import (
    parse_password_vault_scope_json,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabasePasswordVaultReads",)


def _coerce_query_row(row: SQLiteRowDict) -> SQLiteRowDict:
    coerced: SQLiteRowDict = {}
    for key, value in row.items():
        if isinstance(value, bytes):
            try:
                coerced[key] = value.decode("utf-8")
            except UnicodeDecodeError as exception:
                raise StateError("Database row contains invalid utf-8 bytes.") from exception
            continue
        coerced[key] = value
    return coerced


class DatabasePasswordVaultReads:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def list_credentials(
        self,
        user_id: int,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[JSONDict]:
        if not is_strict_user_id(user_id):
            raise ValidationError("Password vault user_id must be positive.")
        if limit <= 0 or limit > 200:
            raise ValidationError("Password vault list limit is out of range.")
        if offset < 0:
            raise ValidationError("Password vault list offset is out of range.")
        normalized_query = normalize_password_vault_search_query(query)

        async def _query_rows(database: aiosqlite.Connection) -> list[SQLiteRowDict]:
            if normalized_query is None:
                rows = await query_to_dicts(
                    database,
                    """
                    SELECT id, label, scope_json, username_hint, created_at_ms, last_used_at_ms
                    FROM webui_password_vault_credentials
                    WHERE user_id = ?
                    ORDER BY created_at_ms DESC
                    LIMIT ? OFFSET ?
                    """,
                    (user_id, limit, offset),
                )
                return [_coerce_query_row(row) for row in rows]
            rows = await query_to_dicts(
                database,
                """
                SELECT id, label, scope_json, username_hint, created_at_ms, last_used_at_ms
                FROM webui_password_vault_credentials
                WHERE user_id = ? AND lower(label) LIKE ?
                ORDER BY created_at_ms DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, f"%{normalized_query}%", limit, offset),
            )
            return [_coerce_query_row(row) for row in rows]

        rows = await self.core.reader.execute_read(_query_rows)
        formatted: list[JSONDict] = []
        for row in rows:
            credential_id_value = row.get("id")
            credential_id = (
                credential_id_value.strip() if isinstance(credential_id_value, str) else ""
            )
            if not credential_id:
                raise StateError("Password vault credential row is missing id.")
            label_raw = row.get("label")
            label_value = label_raw.strip() if isinstance(label_raw, str) else ""
            if not label_value:
                raise StateError("Password vault credential row is missing label.")
            scope_raw_value = row.get("scope_json")
            scope_raw = scope_raw_value.strip() if isinstance(scope_raw_value, str) else ""
            if not scope_raw:
                raise StateError("Password vault credential row is missing scope_json.")
            created_at = coerce_int_from_sqlite(row.get("created_at_ms"))
            if created_at is None or created_at <= 0:
                raise StateError("Password vault credential row has invalid created_at_ms.")
            last_used_at = coerce_int_from_sqlite(row.get("last_used_at_ms"))
            username_hint_raw = row.get("username_hint")
            username_hint = username_hint_raw.strip() if isinstance(username_hint_raw, str) else ""
            scope = parse_password_vault_scope_json(scope_raw)
            scope_payload = coerce_site_scope_json_dict(scope)
            formatted.append(
                {
                    "credential_id": credential_id,
                    "label": label_value,
                    "scope": scope_payload,
                    "username_hint": username_hint or None,
                    "created_at_ms": int(created_at),
                    "last_used_at_ms": int(last_used_at) if last_used_at is not None else None,
                },
            )
        return formatted
