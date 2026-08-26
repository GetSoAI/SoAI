"""SoAI - Hardware history table names [backend/database/repositories/hardware/history_tables.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("HARDWARE_HISTORY_TABLES",)

HARDWARE_HISTORY_TABLES: tuple[str, ...] = (
    "hardware_cpu_history",
    "hardware_gpu_history",
    "hardware_disk_history",
    "hardware_network_history",
)
