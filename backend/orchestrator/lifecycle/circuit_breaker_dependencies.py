"""SoAI - Circuit breaker lifecycle dependencies [backend/orchestrator/lifecycle/circuit_breaker_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorLifecycleCircuitBreakersDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleCircuitBreakersDependencies:
    orchestrator: OrchestratorDependencies
    config: OrchestratorRuntimeConfig
    shutdown_event: asyncio.Event
    state: LifecycleStateAccessorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorLifecycleCircuitBreakersDependencies",
            config=self.config,
            orchestrator=self.orchestrator,
            shutdown_event=self.shutdown_event,
            state=self.state,
        )
