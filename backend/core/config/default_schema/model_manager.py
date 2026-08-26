"""SoAI - Default config schema: model manager [backend/core/config/default_schema/model_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_model_manager_defaults",)


def build_model_manager_defaults() -> ConfigDict:
    return {
        "MANAGER": {
            "PATHS": {
                "MODELS": "models",
            },
            "PARAMETERS": {
                "UPDATE_WORKERS": 4,
                "UPDATE_QUEUE_MAX_SIZE": 20000,
            },
            "PERFORMANCE": {
                "STARTUP_DISCOVERY_TIMEOUT_SEC": 3600,
                "BACKGROUND_REFRESH_INTERVAL_MS": 60000,
            },
            "CACHE": {
                "PARAMETER_MAX_SIZE": 2000,
                "RESOLUTION_TTL_SEC": 300,
                "RESOLUTION_MAX_SIZE": 5000,
            },
        },
    }
