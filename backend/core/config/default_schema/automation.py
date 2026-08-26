"""SoAI - Default config schema: automation [backend/core/config/default_schema/automation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_constants import (
    AUTOMATION_MAX_CONCURRENT_RUNS,
    AUTOMATION_SCHEDULER_DEFAULT_DUE_BATCH_LIMIT,
    AUTOMATION_SCHEDULER_DEFAULT_TICK_SECONDS,
)

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_automation_defaults",)


def build_automation_defaults() -> ConfigDict:
    return {
        "AUTOMATION": {
            "SCHEDULER_TICK_SECONDS": AUTOMATION_SCHEDULER_DEFAULT_TICK_SECONDS,
            "DUE_BATCH_LIMIT": AUTOMATION_SCHEDULER_DEFAULT_DUE_BATCH_LIMIT,
            "MAX_CONCURRENT_RUNS": AUTOMATION_MAX_CONCURRENT_RUNS,
            "MAX_CONCURRENT_RUNS_PER_USER": 1,
            "DISALLOWED_UNQUALIFIED_TOOLS": [],
        },
    }
