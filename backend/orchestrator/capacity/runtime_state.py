"""SoAI - Orchestrator capacity runtime state [backend/orchestrator/capacity/runtime_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import TTLAsyncLockRegistry
from core.concurrency.swappable_resource import SwappableResource
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from orchestrator.capacity.concurrency_limiter import PluginConcurrencyLimiter
from orchestrator.queueing.inference_priority_queue import InferencePriorityQueue

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol
    from core.orchestrator.protocols_queue import QueueCycleManagerProtocol
    from core.tasks.task import Task

__all__ = ("CapacityRuntimeState",)


@dataclass(slots=True)
class CapacityRuntimeState:
    config: OrchestratorRuntimeConfig
    metrics: MetricsManagerProtocol | None
    cycles: QueueCycleManagerProtocol
    plugin_limiters: dict[str, PluginConcurrencyLimiter]
    plugin_queue_resources: dict[str, SwappableResource[InferencePriorityQueue[Task]]]
    stale_plugin_names: set[str]
    plugin_queue_lock: asyncio.Lock
    plugin_queue_locks: TTLAsyncLockRegistry[str]
