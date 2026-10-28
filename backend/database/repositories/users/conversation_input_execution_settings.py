"""SoAI - Conversation input execution settings lineage [backend/database/repositories/users/conversation_input_execution_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json_parsing import parse_json_dict
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "ConversationInputExecutionSettings",
    "query_conversation_input_execution_settings",
    "sync_read_conversation_input_execution_settings",
)

CONVERSATION_INPUT_EXECUTION_SETTINGS_SQL = """
WITH RECURSIVE lineage(input_id, conv_id, user_id, target_input_id, model_settings_json) AS (
    SELECT input_id, conv_id, user_id, target_input_id, model_settings_json
    FROM webui_conversation_inputs
    WHERE input_id = ?
    UNION
    SELECT source.input_id, source.conv_id, source.user_id,
           source.target_input_id, source.model_settings_json
    FROM lineage
    JOIN webui_conversation_inputs AS source
      ON source.input_id = lineage.target_input_id
     AND source.conv_id = lineage.conv_id
     AND source.user_id = lineage.user_id
    WHERE lineage.model_settings_json IS NULL
)
SELECT input_id, model_settings_json
FROM lineage
WHERE model_settings_json IS NOT NULL
LIMIT 1
"""


@dataclass(frozen=True, slots=True)
class ConversationInputExecutionSettings:
    source_input_id: str
    model_settings: JSONDict


def _decode_execution_settings(
    row: SQLiteRowDict | None,
) -> ConversationInputExecutionSettings:
    if row is None:
        raise StateError("Conversation input execution settings are unavailable.")
    source_input_id = row.get("input_id")
    serialized = row.get("model_settings_json")
    if not isinstance(source_input_id, str) or not source_input_id.strip():
        raise StateError("Conversation input execution settings source is invalid.")
    if not isinstance(serialized, str):
        raise StateError("Conversation input execution settings are invalid.")
    try:
        model_settings = parse_json_dict(serialized, field="model_settings_json")
    except ValidationError as exception:
        raise StateError("Conversation input execution settings are invalid.") from exception
    return ConversationInputExecutionSettings(
        source_input_id=source_input_id.strip(),
        model_settings=model_settings,
    )


def sync_read_conversation_input_execution_settings(
    sqlite_conn: sqlite3.Connection,
    input_id: str,
) -> ConversationInputExecutionSettings:
    return _decode_execution_settings(
        sync_fetch_one_as_dict(
            sqlite_conn.execute(CONVERSATION_INPUT_EXECUTION_SETTINGS_SQL, (input_id,)),
        ),
    )


async def query_conversation_input_execution_settings(
    database: aiosqlite.Connection,
    input_id: str,
) -> ConversationInputExecutionSettings:
    return _decode_execution_settings(
        await query_one_to_dict(
            database,
            CONVERSATION_INPUT_EXECUTION_SETTINGS_SQL,
            (input_id,),
        ),
    )
