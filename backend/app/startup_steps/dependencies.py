"""SoAI - Startup step dependencies [backend/app/startup_steps/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.application_dependencies import ApplicationStartupModuleDependencies
from core.app.protocols import ApplicationRuntimeCoordinatorProtocol
from core.di.validation import require_dependencies
from core.timing.startup_timings import StartupTimingsRecorder

__all__ = ("StartupStepDependencies",)


@dataclass(frozen=True, slots=True)
class StartupStepDependencies:
    runtime_coordinator: ApplicationRuntimeCoordinatorProtocol
    module_dependencies: ApplicationStartupModuleDependencies
    startup_timings: StartupTimingsRecorder

    def __post_init__(self) -> None:
        require_dependencies(
            owner="StartupStepDependencies",
            module_dependencies=self.module_dependencies,
            runtime_coordinator=self.runtime_coordinator,
            startup_timings=self.startup_timings,
        )
