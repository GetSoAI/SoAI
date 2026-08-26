"""SoAI - Licensing service composition types [backend/app/types_services_licensing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import httpx2

from app.licensing_repair_plane_coordinator import LicensingRepairPlaneCoordinator
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.trust_material import ReleaseTrustMaterial
from features.licensing.administration_operations import LicensingAdministrationOperations
from features.licensing.deployment_operations import LicensingDeploymentOperations
from features.licensing.maintenance_operations import LicensingMaintenanceOperations
from features.licensing.recovery_actor import LicensingRecoveryActor
from features.licensing.runtime_service import LicensingRuntimeService
from features.licensing.wizard_operations import WizardLicensingOperations


@dataclass(frozen=True, slots=True)
class LicensingServices:
    authority_http_client: httpx2.AsyncClient
    policy: EditionLicensingPolicy
    trust_material: ReleaseTrustMaterial
    runtime: LicensingRuntimeService
    wizard_pending: WizardLicensingOperations
    authenticated_activation: WizardLicensingOperations
    maintenance: LicensingMaintenanceOperations
    deployment_operations: LicensingDeploymentOperations
    administration: LicensingAdministrationOperations
    recovery_actor: LicensingRecoveryActor
    repair_plane_coordinator: LicensingRepairPlaneCoordinator


__all__ = ("LicensingServices",)
