"""SoAI - Hardware history reset persistence [backend/database/repositories/hardware/history_reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.timing.epoch import epoch_ms
from database.core.sql_builders import build_delete_all_statement
from database.repositories.hardware.history_tables import hardware_history_tables
from database.repositories.metrics.genesis import sync_reset_genesis_uptime

__all__ = ("sync_clear_hardware_history",)


def sync_clear_hardware_history(conn: sqlite3.Connection, reset_genesis_uptime: bool) -> int:
    _delete_tables(conn, (*hardware_history_tables(), "hardware_gpu_soaibench_runs"))
    if reset_genesis_uptime:
        sync_reset_genesis_uptime(conn)
    return epoch_ms()


def _delete_tables(conn: sqlite3.Connection, tables: tuple[str, ...]) -> None:
    for table in tables:
        conn.execute(build_delete_all_statement(table=table))
