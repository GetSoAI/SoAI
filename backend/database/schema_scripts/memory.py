"""SoAI - Database schema: memory knowledge graph tables [backend/database/schema_scripts/memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_memory_schema",)


def apply_memory_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS mcp_memory_entities (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            UNIQUE(user_id, name),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_memory_entities_user_type
            ON mcp_memory_entities(user_id, entity_type);
        CREATE TABLE IF NOT EXISTS mcp_memory_observations (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(entity_id) REFERENCES mcp_memory_entities(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_memory_observations_entity
            ON mcp_memory_observations(entity_id);
        CREATE TABLE IF NOT EXISTS mcp_memory_relations (
            id TEXT PRIMARY KEY,
            from_entity_id TEXT NOT NULL,
            to_entity_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(from_entity_id) REFERENCES mcp_memory_entities(id) ON DELETE CASCADE,
            FOREIGN KEY(to_entity_id) REFERENCES mcp_memory_entities(id) ON DELETE CASCADE,
            UNIQUE(from_entity_id, to_entity_id, relation_type)
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_memory_relations_to
            ON mcp_memory_relations(to_entity_id);
        """,
    )
