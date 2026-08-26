"""SoAI - Default config schema: hardware manager [backend/core/config/default_schema/hardware_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_hardware_manager_defaults",)


def build_hardware_manager_defaults() -> ConfigDict:
    return {
        "HARDWARE": {
            "ENABLED": True,
            "GPU_SETTINGS_SLOTS_PATH": "gpu/gpu_settings_slots.json",
            "DISK_FREE_SPACE_TOLERANCE_MB": 750,
            "DISK_RESERVATION_LOCK_TIMEOUT_SEC": 10.0,
            "MONITORING_INTERVAL_MS": 3000,
            "HARDWARE_CACHE_TTL": 2,
            "DETAILED_GPU_INFO": True,
            "HARDWARE_HISTORY_ENABLED": True,
            "DB_RETENTION_HOURS": 168,
            "VARIANT_SPEED_TEMPLATES_REQUIRE_MEASUREMENTS": True,
            "GPU_INFO_CACHE_TTL_SEC": 1,
            "NETWORK_SPEED_CACHE_TTL_SEC": 5,
            "GPU_VENDOR_CACHE_TTL_SEC": 60,
            "MINIMUM_SPECS_WARNING_ENABLED": True,
        },
    }
