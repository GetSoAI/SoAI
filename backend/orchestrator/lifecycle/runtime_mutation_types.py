"""SoAI - Runtime mutation queue typing [backend/orchestrator/lifecycle/runtime_mutation_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.types_system import ConfigReloadedEvent
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.orchestrator.stop_outcome import PluginStopOutcome
from orchestrator.lifecycle.config_reload_result import PluginConfigReloadResult

if TYPE_CHECKING:
    type RuntimeMutationResult = (
        PluginStopOutcome | list[SchedulerWorkItem] | PluginConfigReloadResult | None
    )
    type RuntimeMutationFuture = asyncio.Future[RuntimeMutationResult]
    type DroppedReloadRuntimeMutation = tuple[ConfigReloadedEvent, RuntimeMutationFuture, str]

__all__ = ()
