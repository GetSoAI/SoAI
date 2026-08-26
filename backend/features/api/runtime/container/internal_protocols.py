"""SoAI - Internal protocols for API runtime container wiring [backend/features/api/runtime/container/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.app.protocols import ApplicationControlProtocol
    from core.system.protocols import PowerOperationSupervisorProtocol
    from features.api.runtime.container.api_runtime_services import ApiRuntimeServices
    from features.api.runtime.container.api_runtime_singletons import (
        ApiRuntimeSingletons,
    )
    from features.api.runtime.container.protocol_groups.container_protocols.internal_protocols import (
        MetadataProtocol,
        PathsContainerProtocol,
        RuntimeContainerProtocol,
        SecurityContainerProtocol,
    )
    from features.api.runtime.container.protocol_groups.service_protocols.application.internal_protocols import (
        ApplicationServicesProtocol,
    )

__all__ = (
    "ApiRuntimeServicesBuilderProtocol",
    "MainAppInstanceProtocol",
)


class ApiRuntimeServicesBuilderProtocol(Protocol):
    def __call__(self) -> ApiRuntimeServices: ...


class MainAppInstanceProtocol(Protocol):
    @property
    def application_control(self) -> ApplicationControlProtocol: ...

    @property
    def power_operation_supervisor(self) -> PowerOperationSupervisorProtocol: ...

    @property
    def api_runtime_singletons(self) -> ApiRuntimeSingletons: ...

    @property
    def services(self) -> ApplicationServicesProtocol: ...

    @property
    def runtime(self) -> RuntimeContainerProtocol: ...

    @property
    def paths(self) -> PathsContainerProtocol: ...

    @property
    def security(self) -> SecurityContainerProtocol: ...

    @property
    def metadata(self) -> MetadataProtocol: ...
