"""SoAI - Hardware history reset persistence [backend/database/repositories/hardware/history_reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.core.sql_builders import build_delete_all_statement
from database.repositories.hardware.history_tables import HARDWARE_HISTORY_TABLES

__all__ = ("sync_clear_hardware_history",)


def sync_clear_hardware_history(conn: sqlite3.Connection) -> None:
    _delete_tables(conn, (*HARDWARE_HISTORY_TABLES, "hardware_gpu_soaibench_runs"))


def _delete_tables(conn: sqlite3.Connection, tables: tuple[str, ...]) -> None:
    for table in tables:
        conn.execute(build_delete_all_statement(table=table))
