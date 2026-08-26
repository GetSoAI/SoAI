"""SoAI - Orchestrator plugin queue purge dependency bundle [backend/orchestrator/control/plugin_queue_purge_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from core.di.validation import require_dependencies
from orchestrator.control.queue_scheduler_dependencies import (
    ControlQueueSchedulerDependencies,
)

__all__ = ("PluginQueuePurgeDependencies",)


@dataclass(frozen=True, slots=True)
class PluginQueuePurgeDependencies(ControlQueueSchedulerDependencies):
    @override
    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginQueuePurgeDependencies",
        )
