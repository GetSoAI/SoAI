"""SoAI - Database schema migration from 3 to 4 [backend/database/migrations/schema_3_to_4.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.schema_scripts.agent_prompt_replay import AGENT_PROMPT_REPLAY_SCHEMA_V4
from database.schema_scripts.conversation_attachments import (
    ATTACHMENT_MISSING_CAPABILITIES_COLUMN_SQL,
)
from database.schema_scripts.notifications import apply_notifications_schema
from database.schema_scripts.skills import apply_skills_schema
from database.schema_scripts.webui_chat_storage_schema import (
    CONVERSATION_TITLE_AUTO_UPDATE_ALLOWED_COLUMN_SQL,
)
from database.sql.script import execute_sql_script

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("migrate_database_schema_3_to_4",)


def _rebuild_notifications_schema(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE webui_notifications RENAME TO webui_notifications_schema_3")
    connection.execute("DROP INDEX idx_webui_notifications_user_created")
    connection.execute("DROP INDEX idx_webui_notifications_user_read")
    apply_notifications_schema(connection)
    connection.execute("""INSERT INTO webui_notifications (
            id, user_id, type, title, message, source, link_json, created_at_ms, read_at_ms
        ) SELECT id, user_id, type, title, message, source, link_json, created_at_ms, read_at_ms
        FROM webui_notifications_schema_3""")
    connection.execute("DROP TABLE webui_notifications_schema_3")


def migrate_database_schema_3_to_4(
    connection: sqlite3.Connection,
    logger: LoggerProtocol,
) -> None:
    del logger
    connection.execute(
        """ALTER TABLE webui_agent_turns ADD COLUMN prompt_replay_start_iteration INTEGER
        NOT NULL DEFAULT 0 CHECK(prompt_replay_start_iteration >= 0)"""
    )
    connection.execute(
        "UPDATE webui_agent_turns SET prompt_replay_start_iteration = iteration_index + 1"
    )
    connection.execute(
        f"ALTER TABLE webui_conversations ADD COLUMN {CONVERSATION_TITLE_AUTO_UPDATE_ALLOWED_COLUMN_SQL}"
    )
    connection.execute(
        f"ALTER TABLE webui_conversation_attachments ADD COLUMN {ATTACHMENT_MISSING_CAPABILITIES_COLUMN_SQL}"
    )
    execute_sql_script(connection, AGENT_PROMPT_REPLAY_SCHEMA_V4)
    _rebuild_notifications_schema(connection)
    apply_skills_schema(connection)
    connection.execute("""INSERT INTO webui_skill_snapshots
        (user_id, conv_id, input_id, root_input_id, selection_revision)
        SELECT user_id, conv_id, input_id, input_id, 0 FROM webui_conversation_inputs""")
