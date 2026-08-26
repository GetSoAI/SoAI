"""SoAI - Licensing service graph composition [backend/app/composition/build_licensing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.licensing_repair_plane_coordinator import (
    LicensingRepairPlaneCoordinator,
    LicensingRepairPlaneCoordinatorDependencies,
)
from app.types_services_licensing import LicensingServices
from core.licensing.legal_documents import validate_edition_licensing_documents
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import (
    LicensingRepositoryProtocol,
    LicensingWizardRepositoryProtocol,
)
from core.licensing.trust_material import resolve_release_trust_material
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.runtime.network_http_client import create_guarded_async_http_client
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeRepairPlaneViewProtocol
from core.state.protocols import SystemRestartRequesterProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.users.protocols_database import DatabaseUsersProtocol
from features.licensing.administration_operations import (
    LicensingAdministrationDependencies,
    LicensingAdministrationOperations,
)
from features.licensing.deployment_operations import (
    LicensingDeploymentOperationDependencies,
    LicensingDeploymentOperations,
)
from features.licensing.machine_client import LicensingMachineClient
from features.licensing.maintenance_dependencies import LicensingMaintenanceDependencies
from features.licensing.maintenance_operations import LicensingMaintenanceOperations
from features.licensing.recovery_actor import (
    LicensingRecoveryActor,
    LicensingRecoveryDependencies,
)
from features.licensing.runtime_service import (
    LicensingRuntimeService,
    LicensingRuntimeServiceDependencies,
)
from features.licensing.wizard_operations import (
    WizardLicensingOperationDependencies,
    WizardLicensingOperations,
)


async def build_licensing_services(
    *,
    project_root: str,
    policy: EditionLicensingPolicy,
    repository: LicensingRepositoryProtocol,
    wizard_repository: LicensingWizardRepositoryProtocol,
    database_plugins: DatabasePluginsProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    database_users: DatabaseUsersProtocol,
    runtime_state: RuntimeRepairPlaneViewProtocol,
    restart_requester: SystemRestartRequesterProtocol,
) -> LicensingServices:
    controlling_license = validate_edition_licensing_documents(project_root, policy)
    trust_material = resolve_release_trust_material(project_root)
    authority_http_client = create_guarded_async_http_client(
        runtime_flags,
        source="licensing_authority",
        trust_env=False,
    )
    construction_succeeded = False
    try:
        client = LicensingMachineClient(authority_http_client, "https://soai.to")
        repair_plane_coordinator = LicensingRepairPlaneCoordinator(
            LicensingRepairPlaneCoordinatorDependencies(
                runtime_state=runtime_state,
                restart_requester=restart_requester,
            )
        )
        runtime = LicensingRuntimeService(
            LicensingRuntimeServiceDependencies(
                policy=policy,
                repository=repository,
                wizard_repository=wizard_repository,
                database_plugins=database_plugins,
                trust_material=trust_material,
                controlling_license_fingerprint=controlling_license.fingerprint,
                repair_plane_coordinator=repair_plane_coordinator,
            )
        )
        wizard_pending = WizardLicensingOperations(
            WizardLicensingOperationDependencies(
                policy=policy,
                repository=repository,
                wizard_repository=wizard_repository,
                database_plugins=database_plugins,
                client=client,
                trust_material=trust_material,
                controlling_license_fingerprint=controlling_license.fingerprint,
                document_disposition="pending",
                wizard_mode=True,
            )
        )
        authenticated_activation = WizardLicensingOperations(
            WizardLicensingOperationDependencies(
                policy=policy,
                repository=repository,
                wizard_repository=wizard_repository,
                database_plugins=database_plugins,
                client=client,
                trust_material=trust_material,
                controlling_license_fingerprint=controlling_license.fingerprint,
                document_disposition="active",
                wizard_mode=False,
            )
        )
        maintenance = LicensingMaintenanceOperations(
            LicensingMaintenanceDependencies(
                policy=policy,
                repository=repository,
                database_plugins=database_plugins,
                client=client,
                trust_material=trust_material,
            )
        )
        deployment_operations = LicensingDeploymentOperations(
            LicensingDeploymentOperationDependencies(
                policy=policy,
                repository=repository,
                wizard_repository=wizard_repository,
                database_plugins=database_plugins,
                client=client,
                trust_material=trust_material,
            )
        )
        administration = LicensingAdministrationOperations(
            LicensingAdministrationDependencies(
                policy=policy,
                repository=repository,
                wizard_repository=wizard_repository,
                database_plugins=database_plugins,
                trust_material=trust_material,
            )
        )
        recovery_actor = LicensingRecoveryActor(
            LicensingRecoveryDependencies(
                edition=policy.edition,
                repository=repository,
                wizard_repository=wizard_repository,
                wizard_pending=wizard_pending,
                authenticated_operations=authenticated_activation,
                runtime=runtime,
                trust_material=trust_material,
                cancellation_binder=cancellation_binder,
                finalizer_tracker=finalizer_tracker,
                database_users=database_users,
                repair_plane_coordinator=repair_plane_coordinator,
            )
        )
        services = LicensingServices(
            authority_http_client=authority_http_client,
            policy=policy,
            trust_material=trust_material,
            runtime=runtime,
            wizard_pending=wizard_pending,
            authenticated_activation=authenticated_activation,
            maintenance=maintenance,
            deployment_operations=deployment_operations,
            administration=administration,
            recovery_actor=recovery_actor,
            repair_plane_coordinator=repair_plane_coordinator,
        )
        construction_succeeded = True
        return services
    finally:
        if not construction_succeeded:
            await authority_http_client.aclose()


__all__ = ("build_licensing_services",)
