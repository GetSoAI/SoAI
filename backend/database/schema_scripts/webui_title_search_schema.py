"""SoAI - Database schema: WebUI title search indexes [backend/database/schema_scripts/webui_title_search_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.sql.script import execute_sql_script

__all__ = ("apply_webui_title_search_schema",)

_WEBUI_TITLE_SEARCH_SCHEMA_SQL = """
        CREATE VIRTUAL TABLE IF NOT EXISTS webui_conversation_title_search_fts
            USING fts5(conversation_id UNINDEXED, owner_key, title, tokenize='unicode61');
        CREATE VIRTUAL TABLE IF NOT EXISTS webui_prompt_title_search_fts
            USING fts5(prompt_id UNINDEXED, owner_key, name, tokenize='unicode61');
        CREATE TRIGGER IF NOT EXISTS trg_webui_conversation_title_search_insert
        AFTER INSERT ON webui_conversations
        BEGIN
            INSERT INTO webui_conversation_title_search_fts(conversation_id, owner_key, title)
            VALUES (new.id, 'u' || new.user_id, new.title);
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_conversation_title_search_update
        AFTER UPDATE OF id, title, user_id ON webui_conversations
        WHEN old.id IS NOT new.id OR old.title IS NOT new.title OR old.user_id IS NOT new.user_id
        BEGIN
            DELETE FROM webui_conversation_title_search_fts WHERE conversation_id = old.id;
            INSERT INTO webui_conversation_title_search_fts(conversation_id, owner_key, title)
            VALUES (new.id, 'u' || new.user_id, new.title);
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_conversation_title_search_delete
        AFTER DELETE ON webui_conversations
        BEGIN
            DELETE FROM webui_conversation_title_search_fts WHERE conversation_id = old.id;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_prompt_title_search_insert
        AFTER INSERT ON webui_prompts
        BEGIN
            INSERT INTO webui_prompt_title_search_fts(prompt_id, owner_key, name)
            VALUES (new.id, 'u' || new.user_id, new.name);
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_prompt_title_search_update
        AFTER UPDATE OF id, name, user_id ON webui_prompts
        WHEN old.id IS NOT new.id OR old.name IS NOT new.name OR old.user_id IS NOT new.user_id
        BEGIN
            DELETE FROM webui_prompt_title_search_fts WHERE prompt_id = old.id;
            INSERT INTO webui_prompt_title_search_fts(prompt_id, owner_key, name)
            VALUES (new.id, 'u' || new.user_id, new.name);
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_prompt_title_search_delete
        AFTER DELETE ON webui_prompts
        BEGIN
            DELETE FROM webui_prompt_title_search_fts WHERE prompt_id = old.id;
        END;
        INSERT INTO webui_conversation_title_search_fts(conversation_id, owner_key, title)
        SELECT c.id, 'u' || c.user_id, c.title
          FROM webui_conversations AS c
         WHERE NOT EXISTS (
               SELECT 1
                 FROM webui_conversation_title_search_fts AS f
                WHERE f.conversation_id = c.id
         );
        INSERT INTO webui_prompt_title_search_fts(prompt_id, owner_key, name)
        SELECT p.id, 'u' || p.user_id, p.name
          FROM webui_prompts AS p
         WHERE NOT EXISTS (
               SELECT 1
                 FROM webui_prompt_title_search_fts AS f
                WHERE f.prompt_id = p.id
         );
"""


def apply_webui_title_search_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _WEBUI_TITLE_SEARCH_SCHEMA_SQL)
