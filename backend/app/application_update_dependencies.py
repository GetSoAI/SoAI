"""SoAI - Application update dependencies [backend/app/application_update_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.application_dependencies import ApplicationLogging, ApplicationPaths
from app.edition_composition import UpdaterComposition
from app.internal_protocols import ApplicationRuntimeCoordinatorViewProtocol
from app.types_services import ApplicationServices
from core.di.validation import require_dependencies
from core.runtime.protocols import RuntimeStateStoreProtocol

__all__ = ("ApplicationUpdateServiceDependencies",)


@dataclass(frozen=True, slots=True)
class ApplicationUpdateServiceDependencies:
    logging: ApplicationLogging
    paths: ApplicationPaths
    runtime: RuntimeStateStoreProtocol
    services: ApplicationServices
    runtime_coordinator: ApplicationRuntimeCoordinatorViewProtocol
    updater: UpdaterComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationUpdateServiceDependencies",
            logging=self.logging,
            paths=self.paths,
            runtime=self.runtime,
            runtime_coordinator=self.runtime_coordinator,
            services=self.services,
            updater=self.updater,
        )
