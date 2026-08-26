"""SoAI - MCP access token row normalization helpers [backend/database/repositories/users/mcp_access_token_row_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict
from database.core.row_booleans import coerce_row_bool_or_default
from database.core.sqlite_numbers import coerce_int_from_sqlite

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "normalize_mcp_access_token_row",
    "sanitize_mcp_access_token_row",
)


def normalize_mcp_access_token_row(
    row: SQLiteRowDict | None,
    *,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    if not row:
        return None
    normalized: JSONDict = {}
    normalized["revoked"] = coerce_row_bool_or_default(row.get("revoked"), default=False)
    normalized["created_at_ms"] = coerce_int_from_sqlite(row.get("created_at_ms"))
    normalized["last_used_at_ms"] = coerce_int_from_sqlite(row.get("last_used_at_ms"))
    normalized["expires_at_ms"] = coerce_int_from_sqlite(row.get("expires_at_ms"))
    normalized["revoked_at_ms"] = coerce_int_from_sqlite(row.get("revoked_at_ms"))
    normalized["user_id"] = coerce_int_from_sqlite(row.get("user_id"))
    normalized["revoked_by"] = coerce_int_from_sqlite(row.get("revoked_by"))
    normalized["encryption_version"] = coerce_int_from_sqlite(row.get("encryption_version"))
    encrypted_hash = row.get("hashed_token_ciphertext")
    encrypted_hash_str = str(encrypted_hash) if encrypted_hash is not None else None
    normalized["hashed_token"] = decrypt_hash(encrypted_hash_str)
    for key in (
        "token_id",
        "fingerprint",
        "label",
        "prefix",
        "salt",
    ):
        value = row.get(key)
        normalized[key] = str(value) if value is not None else None
    return normalized


def sanitize_mcp_access_token_row(row: JSONDict | None) -> JSONDict | None:
    payload = coerce_json_dict(row)
    if payload is None:
        return None
    sanitized: JSONDict = {}
    for key, value in payload.items():
        if key in {"hashed_token", "salt", "fingerprint", "encryption_version"}:
            continue
        sanitized[key] = value
    return sanitized
