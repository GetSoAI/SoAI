"""SoAI - Hardware history table names [backend/database/repositories/hardware/history_tables.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("hardware_history_table_for_component", "hardware_history_tables")

_HARDWARE_HISTORY_TABLE_ROWS: tuple[tuple[str, str], ...] = (
    ("cpu", "hardware_cpu_history"),
    ("gpu", "hardware_gpu_history"),
    ("disk", "hardware_disk_history"),
    ("network", "hardware_network_history"),
)


def hardware_history_table_for_component(component: str) -> str | None:
    for selected_component, table in _HARDWARE_HISTORY_TABLE_ROWS:
        if selected_component == component:
            return table
    return None


def hardware_history_tables() -> tuple[str, ...]:
    return tuple(table for _, table in _HARDWARE_HISTORY_TABLE_ROWS)
