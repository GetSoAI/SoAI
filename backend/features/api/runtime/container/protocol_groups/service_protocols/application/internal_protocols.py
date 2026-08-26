"""SoAI - Application services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/application/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from features.api.runtime.container.protocol_groups.service_protocols.configuration.internal_protocols import (
    ConfigurationServicesProtocol,
)
from features.api.runtime.container.protocol_groups.service_protocols.database.internal_protocols import (
    DatabaseServicesProtocol,
)
from features.api.runtime.container.protocol_groups.service_protocols.infrastructure.internal_protocols import (
    InfrastructureServicesProtocol,
)
from features.api.runtime.container.protocol_groups.service_protocols.model.internal_protocols import (
    ModelContextProtocolServicesProtocol,
    ModelServicesProtocol,
)
from features.api.runtime.container.protocol_groups.service_protocols.orchestrator.internal_protocols import (
    OrchestratorServicesProtocol,
)
from features.api.runtime.container.protocol_groups.service_protocols.plugin.internal_protocols import (
    PluginServicesProtocol,
)
from features.api.runtime.container.protocol_groups.service_protocols.storage.internal_protocols import (
    StorageServicesProtocol,
)
from features.api.runtime.container.protocol_groups.service_protocols.task.internal_protocols import (
    TaskServicesProtocol,
)

if TYPE_CHECKING:
    from core.licensing.policy import EditionLicensingPolicy
    from core.licensing.protocols import LicensingRepairPlaneCoordinatorProtocol
    from core.licensing.trust_material import ReleaseTrustMaterial
    from core.os.protocols import HostManagementServicesProtocol
    from features.licensing.administration_operations import LicensingAdministrationOperations
    from features.licensing.deployment_operations import LicensingDeploymentOperations
    from features.licensing.maintenance_operations import LicensingMaintenanceOperations
    from features.licensing.recovery_actor import LicensingRecoveryActor
    from features.licensing.runtime_service import LicensingRuntimeService
    from features.licensing.wizard_operations import WizardLicensingOperations

__all__ = ("ApplicationServicesProtocol", "LicensingServicesProtocol")


class LicensingServicesProtocol(Protocol):
    @property
    def policy(self) -> EditionLicensingPolicy: ...

    @property
    def trust_material(self) -> ReleaseTrustMaterial: ...

    @property
    def runtime(self) -> LicensingRuntimeService: ...

    @property
    def wizard_pending(self) -> WizardLicensingOperations: ...

    @property
    def authenticated_activation(self) -> WizardLicensingOperations: ...

    @property
    def maintenance(self) -> LicensingMaintenanceOperations: ...

    @property
    def deployment_operations(self) -> LicensingDeploymentOperations: ...

    @property
    def administration(self) -> LicensingAdministrationOperations: ...

    @property
    def recovery_actor(self) -> LicensingRecoveryActor: ...

    @property
    def repair_plane_coordinator(self) -> LicensingRepairPlaneCoordinatorProtocol: ...


class ApplicationServicesProtocol(Protocol):
    @property
    def configuration(self) -> ConfigurationServicesProtocol: ...

    @property
    def infrastructure(self) -> InfrastructureServicesProtocol: ...

    @property
    def licensing(self) -> LicensingServicesProtocol: ...

    @property
    def databases(self) -> DatabaseServicesProtocol: ...

    @property
    def tasks(self) -> TaskServicesProtocol: ...

    @property
    def orchestrator(self) -> OrchestratorServicesProtocol: ...

    @property
    def plugins(self) -> PluginServicesProtocol: ...

    @property
    def storage(self) -> StorageServicesProtocol: ...

    @property
    def models(self) -> ModelServicesProtocol: ...

    @property
    def model_context_protocol(self) -> ModelContextProtocolServicesProtocol: ...

    @property
    def host_management(self) -> HostManagementServicesProtocol | None: ...
