"""SoAI - Dependencies for orchestrator model loading lifecycle [backend/orchestrator/lifecycle/model_loading_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.di.validation import require_dependencies
from core.orchestrator.protocols_lifecycle import OrchestratorCircuitBreakersProtocol
from orchestrator.lifecycle.shared_dependencies import LifecycleSharedDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OrchestratorLifecycleModelLoadingDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleModelLoadingDependencies(LifecycleSharedDependencies):
    circuit_breakers: OrchestratorCircuitBreakersProtocol
    health_check_config: JSONDict

    @override
    def __post_init__(self) -> None:
        LifecycleSharedDependencies.__post_init__(self)
        require_dependencies(
            owner="OrchestratorLifecycleModelLoadingDependencies",
            circuit_breakers=self.circuit_breakers,
            health_check_config=self.health_check_config,
        )
