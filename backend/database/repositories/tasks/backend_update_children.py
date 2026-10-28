"""SoAI - Atomic bulk backend update child reservations [backend/database/repositories/tasks/backend_update_children.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.plugins.backend_update_child import BackendUpdateChild
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict
from core.tasks.status_policy import TERMINAL_TASK_STATUS_VALUES
from core.tasks.type_catalog import TASK_TYPE_BACKEND_UPDATE_ALL
from core.types.json import JSONDict
from database.core.savepoints import SQLiteSavepoint

__all__ = ("sync_reserve_backend_update_child",)


def sync_reserve_backend_update_child(
    connection: sqlite3.Connection,
    parent_task_id: str,
    proposed: BackendUpdateChild,
) -> BackendUpdateChild:
    with SQLiteSavepoint(connection, "backend_update_child"):
        row = connection.execute(
            "SELECT task_type, status, metadata FROM unified_tasks WHERE task_id = ?",
            (parent_task_id,),
        ).fetchone()
        if (
            row is None
            or row["status"] in TERMINAL_TASK_STATUS_VALUES
            or row["task_type"] != TASK_TYPE_BACKEND_UPDATE_ALL
        ):
            raise StateError("Bulk backend update parent is no longer active.")
        metadata = (
            parse_json_dict(row["metadata"], field="bulk_task_metadata", reject_duplicate_keys=True)
            if row["metadata"] is not None
            else {}
        )
        children = metadata.get("backend_update_children", {})
        if not isinstance(children, dict):
            raise StateError("Bulk backend update child metadata is corrupt.")
        existing = children.get(proposed.plugin_name)
        if proposed.plugin_name in children:
            if not isinstance(existing, dict) or frozenset(existing) != {
                "request_id",
                "backend_variant_id",
            }:
                raise StateError("Bulk backend update child identity is corrupt.")
            request_id, variant_id = existing["request_id"], existing["backend_variant_id"]
            if not isinstance(request_id, str) or not isinstance(variant_id, str):
                raise StateError("Bulk backend update child identity is invalid.")
            return BackendUpdateChild(proposed.plugin_name, request_id, variant_id)
        child: JSONDict = {
            "request_id": proposed.request_id,
            "backend_variant_id": proposed.backend_variant_id,
        }
        children[proposed.plugin_name] = child
        metadata["backend_update_children"] = children
        connection.execute(
            "UPDATE unified_tasks SET metadata = ? WHERE task_id = ?",
            (serialize_json_compact_stable(metadata), parent_task_id),
        )
        return proposed
