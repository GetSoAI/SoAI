"""SoAI - Default config schema: metrics manager [backend/core/config/default_schema/metrics_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_metrics_manager_defaults",)


def build_metrics_manager_defaults() -> ConfigDict:
    return {
        "METRICS": {
            "CONSERVATIVE_BILLING_CHAR_THRESHOLD": 25,
            "BACKGROUND_QUEUE_MAXSIZE": 100_000,
            "BROADCAST_INTERVAL_MS": 1000,
            "METRICS_HISTORY": {
                "ENABLED": True,
                "LOGGING_INTERVAL_MS": 3000,
                "PRUNING_INTERVAL_SEC": 300,
                "DB_RETENTION_HOURS": 168,
                "MAX_POINTS": 50_000,
                "SUPPORTED_INTERVALS_MS": [
                    3000,
                    60_000,
                    300_000,
                    900_000,
                    3_600_000,
                    21_600_000,
                    86_400_000,
                ],
                "TRACKED_METRICS": [],
            },
            "RESET_GENESIS_ON_CLEAR": False,
        },
    }
