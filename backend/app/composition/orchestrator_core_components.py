"""SoAI - Named orchestrator core component bundle [backend/app/composition/orchestrator_core_components.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from orchestrator.capacity.capacity_service import OrchestratorCapacity
from orchestrator.failover_cooldowns import TransientFailureCooldowns
from orchestrator.lifecycle.service import OrchestratorLifecycle
from orchestrator.queueing.service import OrchestratorQueue
from orchestrator.virtual_model_health import VirtualModelHealth
from orchestrator.virtual_model_rotation import VirtualModelRotation


@dataclass(frozen=True, slots=True)
class OrchestratorCoreComponents:
    config: OrchestratorRuntimeConfig
    shutdown_event: asyncio.Event
    is_quiescent: asyncio.Event
    capacity: OrchestratorCapacity
    transient_failures: TransientFailureCooldowns
    virtual_model_health: VirtualModelHealth
    virtual_model_rotation: VirtualModelRotation
    queue: OrchestratorQueue
    lifecycle: OrchestratorLifecycle


__all__ = ("OrchestratorCoreComponents",)
