"""SoAI - API host composition projection [backend/app/application_host_instance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.application_dependencies import (
    ApplicationMetadata,
    ApplicationPaths,
    ApplicationSecurity,
)
from app.edition_composition import EditionComposition
from app.types_services import ApplicationServices
from core.app.protocols import ApplicationControlProtocol
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.system.protocols import PowerOperationSupervisorProtocol
from features.api.runtime.container.api_runtime_singletons import ApiRuntimeSingletons

__all__ = ("ApplicationHostInstance",)


@dataclass(frozen=True, slots=True)
class ApplicationHostInstance:
    metadata: ApplicationMetadata
    paths: ApplicationPaths
    runtime: RuntimeStateStoreProtocol
    security: ApplicationSecurity
    services: ApplicationServices
    api_runtime_singletons: ApiRuntimeSingletons
    application_control: ApplicationControlProtocol
    power_operation_supervisor: PowerOperationSupervisorProtocol
    edition_composition: EditionComposition
