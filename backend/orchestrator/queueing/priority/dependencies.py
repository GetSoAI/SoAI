"""SoAI - Dependency container for priority queue management [backend/orchestrator/queueing/priority/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.metrics.protocols import MetricsManagerProtocol
from core.orchestrator.protocols_queue import QueueCycleManagerProtocol
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task

__all__ = ("QueuePriorityDependencies",)


@dataclass(frozen=True, slots=True)
class QueuePriorityDependencies:
    config: OrchestratorRuntimeConfig
    metrics: MetricsManagerProtocol | None
    cycles: QueueCycleManagerProtocol
    shutdown_event: asyncio.Event
    get_total_backlog_size: Callable[[], Awaitable[int]]
    require_orchestration_context: Callable[[Task], OrchestrationContext]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="QueuePriorityDependencies",
            config=self.config,
            cycles=self.cycles,
            shutdown_event=self.shutdown_event,
            get_total_backlog_size=self.get_total_backlog_size,
            require_orchestration_context=self.require_orchestration_context,
        )
