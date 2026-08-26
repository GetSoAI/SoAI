"""SoAI - Plugin guardian internal protocol [backend/plugins/protocols_internal/guardian/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from typing import TYPE_CHECKING, ClassVar, Protocol

from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.orchestrator.routing_config import RoutingConfig
    from core.plugins.protocols import PluginManagerProtocol
    from core.plugins.protocols_guardian import (
        DirectorComponentContext,
        GuardianExecutorProtocol,
    )
    from core.state.protocols import StateAggregatorProtocol
    from core.tasks.protocols import TaskCancellationBinderProtocol

__all__ = ("PluginGuardianInternalProtocol",)


class PluginGuardianInternalProtocol(Protocol):
    orchestrator: OrchestratorLifecycleProtocol
    executor: GuardianExecutorProtocol
    plugin_manager: PluginManagerProtocol
    state_aggregator: StateAggregatorProtocol
    metrics: MetricsManagerProtocol | None
    audit_logger: LoggerProtocol
    routing_config: RoutingConfig
    state_history: dict[str, deque[tuple[str, float]]]
    bus: EventBusProtocol
    FLAPPING_FAILURE_STATES: ClassVar[frozenset[str]]

    @property
    def recovery_tasks(self) -> dict[str, asyncio.Task[None]]: ...

    @property
    def recovery_tasks_lock(self) -> asyncio.Lock: ...

    @property
    def recovery_initiation_lock(self) -> asyncio.Lock: ...

    @property
    def component_context(self) -> DirectorComponentContext: ...

    @property
    def shutdown_event(self) -> asyncio.Event: ...

    @property
    def cancellation_binder(self) -> TaskCancellationBinderProtocol: ...

    async def guarded_recover_plugin(self, plugin_name: str, reason: str) -> None: ...
