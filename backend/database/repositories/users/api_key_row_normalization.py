"""SoAI - OpenAI API key row normalization helpers [backend/database/repositories/users/api_key_row_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict, coerce_str_list
from core.validation.epoch import require_unix_epoch_ms
from database.core.json_codec import safe_json_deserialize
from database.core.row_booleans import coerce_row_bool_or_default
from database.core.sqlite_numbers import (
    coerce_int_from_sqlite,
    coerce_non_negative_int_from_sqlite,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = (
    "normalize_api_key_row",
    "sanitize_api_key_row",
)


def normalize_api_key_row(
    row: SQLiteRowDict | None,
    *,
    now_ts: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    if not row:
        return None
    normalized: JSONDict = {}
    normalized["revoked"] = _require_revoked_flag(row.get("revoked"))
    for field in (
        "created_at_ms",
        "last_used_at_ms",
        "revoked_at_ms",
        "expires_at_ms",
    ):
        normalized[field] = coerce_int_from_sqlite(row.get(field))
    rotation_reminder = _require_rotation_reminder(row.get("rotation_reminder_at_ms"))
    normalized["rotation_reminder_at_ms"] = rotation_reminder
    normalized["request_count"] = coerce_non_negative_int_from_sqlite(row.get("request_count"))
    normalized["rate_limited_count"] = coerce_non_negative_int_from_sqlite(
        row.get("rate_limited_count"),
    )
    last_used_ip = row.get("last_used_ip")
    normalized["last_used_ip"] = str(last_used_ip) if last_used_ip is not None else None
    normalized["scopes"] = _decode_scopes(row.get("scopes"))
    encrypted_hash = row.get("hashed_key_ciphertext")
    encrypted_hash_str = str(encrypted_hash) if encrypted_hash is not None else None
    normalized["hashed_key"] = decrypt_hash(encrypted_hash_str)
    normalized["rotation_due"] = rotation_reminder is not None and rotation_reminder <= int(now_ts)
    for key in (
        "key_id",
        "fingerprint",
        "label",
        "prefix",
        "salt",
        "encryption_version",
    ):
        value = row.get(key)
        normalized[key] = str(value) if value is not None else None
    normalized["created_by"] = coerce_int_from_sqlite(row.get("created_by"))
    normalized["revoked_by"] = coerce_int_from_sqlite(row.get("revoked_by"))
    normalized["assigned_user_id"] = coerce_int_from_sqlite(row.get("assigned_user_id"))
    return normalized


def _require_revoked_flag(value: JSONValue) -> bool:
    return coerce_row_bool_or_default(value, default=False)


def _require_rotation_reminder(value: SQLiteValue) -> int | None:
    if value is None:
        return None
    try:
        return require_unix_epoch_ms(
            value,
            error_message="OpenAI API key rotation reminder must be epoch milliseconds.",
        )
    except ValidationError as exception:
        raise sqlite3.DatabaseError(
            "OpenAI API key row contains an invalid rotation reminder.",
        ) from exception


def _decode_scopes(value: SQLiteValue) -> list[str]:
    if value is None:
        return []
    decoded = safe_json_deserialize(value, None)
    if decoded is None:
        return []
    scopes = coerce_str_list(decoded, strip_items=True)
    if scopes is None:
        raise ValidationError("OpenAI API key field 'scopes' is invalid.")
    for index, scope in enumerate(scopes):
        if not scope:
            raise ValidationError(f"OpenAI API key field 'scopes[{index}]' is invalid.")
    return scopes


def sanitize_api_key_row(row: JSONDict | None) -> JSONDict | None:
    if not row:
        return None
    payload = coerce_json_dict(row)
    if payload is None:
        return None
    sanitized: JSONDict = {}
    for key, value in payload.items():
        if key in {"hashed_key", "salt", "fingerprint", "encryption_version"}:
            continue
        sanitized[key] = value
    return sanitized
