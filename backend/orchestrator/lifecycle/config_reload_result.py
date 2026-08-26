"""SoAI - Plugin config reload result model [backend/orchestrator/lifecycle/config_reload_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.orchestrator.scheduler_work import SchedulerWorkItem

__all__ = (
    "PluginConfigReloadOutcome",
    "PluginConfigReloadResult",
)


class PluginConfigReloadOutcome(Enum):
    APPLIED = "applied"
    DEFERRED = "deferred"
    SUPERSEDED = "superseded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


@dataclass(frozen=True, slots=True)
class PluginConfigReloadResult:
    outcome: PluginConfigReloadOutcome
    work_items: tuple[SchedulerWorkItem, ...] = field(default_factory=tuple)
    error: str | None = None

    @property
    def should_retry(self) -> bool:
        return self.outcome in {
            PluginConfigReloadOutcome.DEFERRED,
            PluginConfigReloadOutcome.FAILED_RETRYABLE,
        }
