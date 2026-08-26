"""SoAI - Default config schema: inactivity monitor [backend/core/config/default_schema/inactivity_monitor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_inactivity_monitor_defaults",)


def build_inactivity_monitor_defaults() -> ConfigDict:
    return {
        "INACTIVITY": {
            "CHECK_INTERVAL_SEC": 15,
            "SYSTEM": {
                "ENABLED": False,
                "TIMEOUT_MINUTES": 30,
                "ACTION": "shutdown",
            },
            "MODELS": {
                "ENABLED": False,
                "TIMEOUT_MINUTES": 10,
            },
        },
    }
