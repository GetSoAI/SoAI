"""SoAI - Plugin subsystem dependency bundles [backend/core/plugins/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
from core.plugins.protocols_guardian import (
    DirectorComponentContext,
    GuardianExecutorProtocol,
)

__all__ = ("PluginGuardianDependencies",)


@dataclass(frozen=True, slots=True)
class PluginGuardianDependencies:
    orchestrator: OrchestratorLifecycleProtocol
    executor: GuardianExecutorProtocol
    component_context: DirectorComponentContext

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginGuardianDependencies",
            component_context=self.component_context,
            executor=self.executor,
            orchestrator=self.orchestrator,
        )
