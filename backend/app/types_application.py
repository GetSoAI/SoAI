"""SoAI - High-level application container types [backend/app/types_application.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import (
    ApplicationEnvironment,
    ApplicationLogging,
    ApplicationMetadata,
    ApplicationModuleDependencies,
    ApplicationPaths,
    ApplicationSecurity,
)
from app.edition_composition import EditionComposition
from app.types_services import ApplicationServices
from core.runtime.protocols import RuntimeStateStoreProtocol

if TYPE_CHECKING:
    from features.api.runtime.container.api_runtime_singletons import (
        ApiRuntimeSingletons,
    )

__all__ = (
    "ApplicationAssembly",
    "ApplicationContext",
)


@dataclass(slots=True, frozen=True)
class ApplicationContext:
    logging: ApplicationLogging
    runtime: RuntimeStateStoreProtocol
    api_runtime_singletons: ApiRuntimeSingletons
    paths: ApplicationPaths
    services: ApplicationServices
    edition_composition: EditionComposition


@dataclass(slots=True, frozen=True)
class ApplicationAssembly:
    environment: ApplicationEnvironment
    metadata: ApplicationMetadata
    paths: ApplicationPaths
    logging: ApplicationLogging
    security: ApplicationSecurity
    runtime: RuntimeStateStoreProtocol
    api_runtime_singletons: ApiRuntimeSingletons
    services: ApplicationServices
    module_dependencies: ApplicationModuleDependencies
    edition_composition: EditionComposition
