"""SoAI - Shared memory graph row insertion [backend/database/repositories/memory/graph_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

__all__ = (
    "sync_insert_memory_entity",
    "sync_insert_memory_observation",
)


def sync_insert_memory_entity(
    conn: sqlite3.Connection,
    entity_id: str,
    user_id: int,
    name: str,
    entity_type: str,
    created_at_ms: int,
) -> None:
    conn.execute(
        "INSERT INTO mcp_memory_entities (id, user_id, name, entity_type, created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
        (entity_id, user_id, name, entity_type, created_at_ms, created_at_ms),
    )


def sync_insert_memory_observation(
    conn: sqlite3.Connection,
    observation_id: str,
    entity_id: str,
    content: str,
    source: str | None,
    created_at_ms: int,
) -> None:
    conn.execute(
        "INSERT INTO mcp_memory_observations (id, entity_id, content, source, created_at_ms) VALUES (?, ?, ?, ?, ?)",
        (observation_id, entity_id, content, source, created_at_ms),
    )
