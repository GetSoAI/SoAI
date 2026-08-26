"""SoAI - Degraded-mode bootstrap configuration defaults [backend/app/bootstrap_degraded_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.meta.paths import join_data_abs
from core.network.hosts import bind_all_interfaces_host_v4

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_degraded_bootstrap_config",)


def build_degraded_bootstrap_config(*, base_dir: str) -> ConfigDict:
    base_path = os.path.abspath(base_dir)
    data_path = join_data_abs(base_path)
    return {
        "SYSTEM": {
            "PATHS": {
                "BASE": base_dir,
                "SYSTEM_DATA": data_path,
                "TEMP": join_data_abs(base_path, "temp"),
                "LOCKS": join_data_abs(base_path, "locks"),
                "SYSTEM_ENCRYPTION_KEY": join_data_abs(base_path, "secret.key"),
            },
            "HARDWARE": {
                "GPU_SETTINGS_SLOTS_PATH": join_data_abs(
                    base_path,
                    "gpu",
                    "gpu_settings_slots.json",
                ),
            },
        },
        "SERVER": {
            "HTTP": {
                "ENABLED": True,
                "NETWORK": {"HOST": "127.0.0.1", "PORT": 5090},
            },
            "WEBUI": {
                "ENABLED": True,
                "HOST": bind_all_interfaces_host_v4(),
                "PATH": "frontend",
                "FALLBACK_PATHS": [],
                "WALLPAPER_MAX_SIZE_MB": 25,
                "AUTO_OPEN_BROWSER": True,
            },
        },
        "MODELS": {
            "MANAGER": {
                "PATHS": {"MODELS": join_data_abs(base_path, "models")},
                "PERFORMANCE": {"STARTUP_DISCOVERY_TIMEOUT_SEC": 3600},
            },
        },
        "PLUGINS": {
            "PATHS": {
                "PLUGINS": os.path.join(base_path, "plugins"),
                "BACKENDS": join_data_abs(base_path, "backends"),
                "PLUGIN_LOGS": join_data_abs(base_path, "logs", "plugins"),
                "TEMPLATES": join_data_abs(base_path, "templates"),
            },
        },
        "DATA": {
            "DATABASE": {"PATHS": {"SYSTEM_DB": join_data_abs(base_path, "database", "soai.db")}},
            "FILES": {"PATHS": {"FILES_STORAGE": join_data_abs(base_path, "files")}},
            "BACKUP": {
                "BACKUPS_PATH": join_data_abs(base_path, "backups"),
            },
        },
        "OBSERVABILITY": {
            "LOGGING": {
                "LOG_LEVEL": "INFO",
                "LOGS_PATH": join_data_abs(base_path, "logs"),
                "ENABLE_ROTATION": True,
            },
        },
    }
