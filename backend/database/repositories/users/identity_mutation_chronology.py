"""SoAI - Identity mutation database chronology validation [backend/database/repositories/users/identity_mutation_chronology.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3


def sync_identity_mutation_chronology_is_valid(
    conn: sqlite3.Connection,
    observed_at_ms: int,
) -> bool:
    row = conn.execute(
        """
        SELECT MAX(value) AS watermark FROM (
            SELECT MAX(created_at_ms) AS value
            FROM webui_device_sessions
            WHERE expires_at_ms > ?
            UNION ALL
            SELECT MAX(rotated_at_ms)
            FROM webui_session_rotations
            WHERE source_expires_at_ms > ?
               OR replacement_expires_at_ms > ?
               OR recoverable_until_ms > ?
        )
        """,
        (observed_at_ms, observed_at_ms, observed_at_ms, observed_at_ms),
    ).fetchone()
    return row is None or row["watermark"] is None or int(row["watermark"]) <= observed_at_ms


__all__ = ("sync_identity_mutation_chronology_is_valid",)
