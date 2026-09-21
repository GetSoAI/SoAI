"""SoAI - Durable SoAIBench installation identity [backend/database/repositories/hardware/soaibench_installation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.errors.exceptions import DatabaseError
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONValue
from database.core.json_codec import safe_json_deserialize

__all__ = (
    "sync_get_or_create_soaibench_installation_id",
    "validate_soaibench_installation_id",
)

SETTING_KEY = "soaibench.installation_id"


def sync_get_or_create_soaibench_installation_id(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT value FROM webui_system_settings WHERE key=?",
        (SETTING_KEY,),
    ).fetchone()
    if row is None:
        candidate = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO webui_system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
            (SETTING_KEY, serialize_json_compact_stable_strict(candidate)),
        )
        row = connection.execute(
            "SELECT value FROM webui_system_settings WHERE key=?",
            (SETTING_KEY,),
        ).fetchone()
    if row is None:
        raise DatabaseError(
            "SoAIBench installation identity could not be persisted.",
            operation="hardware.soaibench.installation_identity",
        )
    return validate_soaibench_installation_id(safe_json_deserialize(row[0], None))


def validate_soaibench_installation_id(value: JSONValue | None) -> str:
    if not isinstance(value, str):
        raise DatabaseError(
            "Stored SoAIBench installation identity is invalid.",
            operation="hardware.soaibench.installation_identity",
        )
    try:
        parsed = uuid.UUID(value)
    except ValueError as exception:
        raise DatabaseError(
            "Stored SoAIBench installation identity is invalid.",
            operation="hardware.soaibench.installation_identity",
            cause=exception,
        ) from exception
    if parsed.version != 4 or str(parsed) != value:
        raise DatabaseError(
            "Stored SoAIBench installation identity is invalid.",
            operation="hardware.soaibench.installation_identity",
        )
    return value
