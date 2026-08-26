"""SoAI - Default config schema: plugin manager [backend/core/config/default_schema/plugin_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_plugin_manager_defaults",)


def build_plugin_manager_defaults() -> ConfigDict:
    return {
        "PLUGINS": {
            "PATHS": {
                "PLUGINS": "plugins",
                "BACKENDS": "backends",
                "VENVS_ROOT": "plugins/venvs",
                "PLUGIN_LOGS": "logs/plugins",
                "TEMPLATES": "templates",
            },
            "FEATURES": {
                "UPLOADS": True,
                "DOWNLOADS": True,
            },
            "SECURITY": {
                "ALLOW_INSECURE_DOWNLOADS": False,
                "SAFETY_VALIDATION": True,
            },
            "PERFORMANCE": {
                "STARTUP_CONCURRENCY": 10,
                "BACKEND_DRIFT_SCAN_COOLDOWN_SEC": 5.0,
            },
            "AUTHORITATIVE_STATE": {
                "OUTBOX": {
                    "SHUTDOWN_DRAIN_TIMEOUT_SEC": 18.0,
                },
            },
            "RECOVERY": {
                "STARTUP_STOP_TIMEOUT_SEC": 30.0,
            },
            "STOP_START_TASK_CANCEL_TIMEOUT_SEC": 10.0,
        },
    }
