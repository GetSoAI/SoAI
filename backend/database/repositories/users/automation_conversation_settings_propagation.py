"""SoAI - Automation conversation settings propagation [backend/database/repositories/users/automation_conversation_settings_propagation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.automation.automation_mutation_results import AutomationConversationVersion
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.core.json_codec import serialize_required_json_object_field

__all__ = ("sync_propagate_automation_conversation_model_settings",)

_LINKED_CONVERSATION_IDS_SQL = """
    SELECT conv_id FROM automation_runs
    WHERE automation_id = ? AND user_id = ? AND conv_id IS NOT NULL
"""


def sync_propagate_automation_conversation_model_settings(
    conn: sqlite3.Connection,
    automation_id: str,
    user_id: int,
    model_settings: JSONDict,
) -> tuple[AutomationConversationVersion, ...]:
    serialized = serialize_required_json_object_field(
        model_settings,
        error_message="Automation conversation model_settings are invalid.",
    )
    now_ms = epoch_ms()
    conn.execute(
        f"""
        UPDATE webui_conversations
        SET model_settings = ?,
            last_modified_at_ms = MAX(last_modified_at_ms + 1, ?)
        WHERE user_id = ? AND id IN ({_LINKED_CONVERSATION_IDS_SQL})
        """,
        (serialized, now_ms, user_id, automation_id, user_id),
    )
    rows = conn.execute(
        f"""
        SELECT id, last_modified_at_ms
        FROM webui_conversations
        WHERE user_id = ? AND id IN ({_LINKED_CONVERSATION_IDS_SQL})
        ORDER BY id
        """,
        (user_id, automation_id, user_id),
    ).fetchall()
    return tuple(
        AutomationConversationVersion(
            conv_id=str(row[0]),
            last_modified_at_ms=int(row[1]),
        )
        for row in rows
    )
