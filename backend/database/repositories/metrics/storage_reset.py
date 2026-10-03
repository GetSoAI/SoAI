"""SoAI - Atomic metrics storage reset [backend/database/repositories/metrics/storage_reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.timing.epoch import epoch_ms
from database.repositories.metrics.genesis import sync_reset_genesis_counters

__all__ = ("sync_reset_metrics_storage",)


def sync_reset_metrics_storage(conn: sqlite3.Connection, reset_genesis_counters: bool) -> int:
    conn.execute("DELETE FROM metrics_live")
    conn.execute("DELETE FROM metrics_history")
    if reset_genesis_counters:
        sync_reset_genesis_counters(conn)
    return epoch_ms()
