"""SoAI - Domain event outbox schema (transactional outbox) [backend/database/schema_scripts/domain_event_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.schema_scripts.outbox_support import apply_transactional_outbox_schema

__all__ = ("apply_domain_event_outbox_schema",)


def apply_domain_event_outbox_schema(conn: sqlite3.Connection) -> None:
    apply_transactional_outbox_schema(
        conn,
        table_name="webui_domain_event_outbox",
        pending_index_name="idx_webui_domain_event_outbox_pending",
        processing_index_name="idx_webui_domain_event_outbox_processing_timeout",
    )
