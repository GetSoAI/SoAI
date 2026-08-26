"""SoAI - Authoritative plugin state outbox schema [backend/database/schema_scripts/authoritative_plugin_state/outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.schema_scripts.outbox_support import apply_transactional_outbox_schema

__all__ = ("apply_authoritative_plugin_state_outbox_schema",)


def apply_authoritative_plugin_state_outbox_schema(conn: sqlite3.Connection) -> None:
    apply_transactional_outbox_schema(
        conn,
        table_name="plugin_authoritative_state_outbox",
        pending_index_name="idx_plugin_authoritative_state_outbox_pending",
        processing_index_name="idx_plugin_authoritative_state_outbox_processing_timeout",
        extra_columns_sql="plugin_name TEXT NOT NULL REFERENCES plugins_catalog(plugin_name) ON DELETE CASCADE,\n            ",
    )
