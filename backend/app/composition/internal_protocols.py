"""SoAI - App assembly internal protocols [backend/app/composition/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.types_services_database import DatabaseServices
    from app.types_services_foundation import (
        ConfigurationServices,
        InfrastructureServices,
        TaskServices,
    )
    from app.types_services_runtime import HostManagementServices
    from core.state.protocols import SystemRestartRequesterProtocol

__all__ = ("HostManagementServiceBuilderProtocol",)


class HostManagementServiceBuilderProtocol(Protocol):
    def __call__(
        self,
        *,
        configuration_services: ConfigurationServices,
        infrastructure_services: InfrastructureServices,
        database_services: DatabaseServices,
        task_services: TaskServices,
        system_restart_requester: SystemRestartRequesterProtocol | None,
    ) -> HostManagementServices: ...
