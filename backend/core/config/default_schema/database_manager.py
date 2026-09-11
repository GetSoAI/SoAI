"""SoAI - Default config schema: database manager [backend/core/config/default_schema/database_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("DEFAULT_VACUUM_INTERVAL_HOURS", "build_database_manager_defaults")

DEFAULT_VACUUM_INTERVAL_HOURS = 720


def build_database_manager_defaults() -> ConfigDict:
    return {
        "DATABASE": {
            "SQLITE": {
                "CONNECT_TIMEOUT_SEC": 10,
                "VACUUM_INTERVAL_HOURS": DEFAULT_VACUUM_INTERVAL_HOURS,
                "READ_POOL_MAX_SIZE": 8,
                "READ_MMAP_SIZE_MB": 4096,
                "WRITE_MMAP_SIZE_MB": 4096,
            },
            "WRITER": {
                "INIT_TIMEOUT_SEC": 30,
                "SHUTDOWN_TIMEOUT_SEC": 5,
                "OPERATION_TIMEOUT_SEC": 120,
            },
            "METRICS": {
                "IO_LOGGING": False,
                "IO_SAMPLE_INTERVAL_SEC": 1,
            },
        },
    }
