"""SoAI - Dependency bundle for orchestrator queueing service [backend/orchestrator/queueing/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.protocols_queue import QueueCycleManagerProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.queueing.scheduling_clock import QueueSchedulingClock
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorQueueDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorQueueDependencies:
    orchestrator: OrchestratorDependencies
    config: OrchestratorRuntimeConfig
    routing_config: RoutingConfig
    cycles: QueueCycleManagerProtocol
    task_registry: TaskRegistryProtocol
    scheduling_clock: QueueSchedulingClock
    shutdown_event: asyncio.Event
    is_quiescent: asyncio.Event

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorQueueDependencies",
            config=self.config,
            cycles=self.cycles,
            is_quiescent=self.is_quiescent,
            orchestrator=self.orchestrator,
            routing_config=self.routing_config,
            scheduling_clock=self.scheduling_clock,
            shutdown_event=self.shutdown_event,
            task_registry=self.task_registry,
        )
