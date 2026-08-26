"""SoAI - Chat preset SQL row reading and projection [backend/database/repositories/users/chat_preset_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.chat_presets.contracts import ChatPresetListResult, ChatPresetProjectedRecord
from core.chat_presets.stored_projection import (
    ChatPresetStoredIntegrityError,
    project_stored_chat_preset,
)
from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from database.core.query_execution import query_to_dicts
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.repositories.row_formatting import format_row

__all__ = (
    "list_chat_preset_rows",
    "project_chat_preset_row",
    "read_owned_chat_preset_row",
)

_SELECT_FIELDS = """
    id, user_id, name, name_key, sections_json, revision,
    created_at_ms, modified_at_ms
"""


def project_chat_preset_row(row: JSONDict) -> ChatPresetProjectedRecord:
    try:
        return project_stored_chat_preset(row)
    except (TypeError, ValueError) as exception:
        raise StateError("Chat preset row projection failed.") from exception


def read_owned_chat_preset_row(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    preset_id: str,
) -> JSONDict | None:
    row = conn.execute(
        f"""
        SELECT {_SELECT_FIELDS}
        FROM webui_chat_presets
        WHERE id = ? AND user_id = ?
        """,
        (preset_id, user_id),
    ).fetchone()
    return format_row(dict(row)) if row is not None else None


async def list_chat_preset_rows(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> ChatPresetListResult:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {_SELECT_FIELDS}
        FROM webui_chat_presets
        WHERE user_id = ?
        ORDER BY modified_at_ms DESC, name_key ASC, id ASC
        """,
        (user_id,),
    )
    presets: list[ChatPresetProjectedRecord] = []
    structurally_invalid_count = 0
    for row in rows:
        try:
            presets.append(project_chat_preset_row(sqlite_row_dict_to_json_dict(row)))
        except (ChatPresetStoredIntegrityError, StateError, ValidationError):
            structurally_invalid_count += 1
    return {
        "presets": presets,
        "structurally_invalid_count": structurally_invalid_count,
    }
