"""SoAI - Orchestrator capacity dependency container [backend/orchestrator/capacity/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.orchestrator.protocols_queue import QueueCycleManagerProtocol
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = ("OrchestratorCapacityDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorCapacityDependencies:
    config: OrchestratorRuntimeConfig
    metrics: MetricsManagerProtocol | None
    cycles: QueueCycleManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorCapacityDependencies",
            config=self.config,
            cycles=self.cycles,
        )
