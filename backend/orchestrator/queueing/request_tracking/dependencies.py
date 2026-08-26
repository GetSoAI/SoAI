"""SoAI - Request tracking dependencies [backend/orchestrator/queueing/request_tracking/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task

__all__ = ("QueueRequestTrackingDependencies",)


@dataclass(frozen=True, slots=True)
class QueueRequestTrackingDependencies:
    require_orchestration_context: Callable[[Task], OrchestrationContext]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="QueueRequestTrackingDependencies",
            require_orchestration_context=self.require_orchestration_context,
        )
