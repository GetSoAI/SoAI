"""SoAI - Licensing maintenance dependency contract [backend/features/licensing/maintenance_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import LicensingRepositoryProtocol
from core.licensing.trust_material import ReleaseTrustMaterial
from core.plugins.protocols_database import DatabasePluginsProtocol
from features.licensing.machine_client import LicensingMachineClient

__all__ = ("LicensingMaintenanceDependencies",)


@dataclass(frozen=True, slots=True)
class LicensingMaintenanceDependencies:
    policy: EditionLicensingPolicy
    repository: LicensingRepositoryProtocol
    database_plugins: DatabasePluginsProtocol
    client: LicensingMachineClient
    trust_material: ReleaseTrustMaterial

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LicensingMaintenanceDependencies",
            client=self.client,
            database_plugins=self.database_plugins,
            policy=self.policy,
            repository=self.repository,
            trust_material=self.trust_material,
        )
