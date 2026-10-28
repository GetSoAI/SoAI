"""SoAI - Atomic incident memory relationship management [backend/database/repositories/memory/relation_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.memory.revisions import memory_management_error
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.repositories.memory.entry_mutations import require_entry_revision, require_memory_text
from database.repositories.memory.management_snapshots import sync_read_managed_entry
from database.repositories.memory.write_queries_graph_delete import sync_delete_graph

__all__ = (
    "require_incident_relation",
    "sync_update_relation",
    "sync_delete_relation",
)


def require_incident_relation(entry: JSONDict, relation_id: str) -> JSONDict:
    relations = entry.get("relations")
    if isinstance(relations, list):
        for relation in relations:
            if isinstance(relation, dict) and relation.get("id") == relation_id:
                return relation
    raise memory_management_error(
        "memory_relation_missing",
        "This relationship no longer belongs to this memory. Refresh and review the entry.",
        404,
    )


def sync_update_relation(
    conn: sqlite3.Connection,
    user_id: int,
    entry_id: str,
    relation_id: str,
    expected_revision: str,
    from_entity_id: str,
    to_entity_id: str,
    relation_type: str,
) -> JSONDict:
    entry = require_entry_revision(conn, user_id, entry_id, expected_revision)
    previous = require_incident_relation(entry, relation_id)
    normalized_type = require_memory_text(relation_type, "relation_type")
    if entry_id not in (from_entity_id, to_entity_id):
        raise memory_management_error(
            "memory_relation_not_incident", "Keep one endpoint connected to this memory.", 422
        )
    for endpoint_id in (from_entity_id, to_entity_id):
        if (
            conn.execute(
                "SELECT 1 FROM mcp_memory_entities WHERE id = ? AND user_id = ?",
                (endpoint_id, user_id),
            ).fetchone()
            is None
        ):
            raise memory_management_error(
                "memory_endpoint_missing", "Select endpoints from your current memory library.", 404
            )
    duplicate = conn.execute(
        "SELECT id FROM mcp_memory_relations WHERE from_entity_id = ? AND to_entity_id = ? AND relation_type = ? AND id != ?",
        (from_entity_id, to_entity_id, normalized_type, relation_id),
    ).fetchone()
    if duplicate is not None:
        raise memory_management_error(
            "memory_duplicate_relation",
            "This relationship already exists. Choose different endpoints or a different type.",
        )
    conn.execute(
        "UPDATE mcp_memory_relations SET from_entity_id = ?, to_entity_id = ?, relation_type = ? WHERE id = ?",
        (from_entity_id, to_entity_id, normalized_type, relation_id),
    )
    now = epoch_ms()
    for endpoint_id in (
        from_entity_id,
        to_entity_id,
        str(previous["from_entity_id"]),
        str(previous["to_entity_id"]),
    ):
        conn.execute(
            "UPDATE mcp_memory_entities SET updated_at_ms = ? WHERE id = ?", (now, endpoint_id)
        )
    return sync_read_managed_entry(conn, user_id, entry_id)


def sync_delete_relation(
    conn: sqlite3.Connection, user_id: int, entry_id: str, relation_id: str, expected_revision: str
) -> JSONDict:
    entry = require_entry_revision(conn, user_id, entry_id, expected_revision)
    relation = require_incident_relation(entry, relation_id)
    result = sync_delete_graph(conn, user_id, [], [], [relation_id])
    now = epoch_ms()
    for endpoint_id in (str(relation["from_entity_id"]), str(relation["to_entity_id"])):
        conn.execute(
            "UPDATE mcp_memory_entities SET updated_at_ms = ? WHERE id = ?", (now, endpoint_id)
        )
    return result
