"""SoAI - Authenticated licensing declaration administration [backend/features/licensing/administration_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.licensing.entitlement_payloads import ParsedEntitlementPayload
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import (
    LicensingRepositoryProtocol,
    LicensingWizardRepositoryProtocol,
)
from core.licensing.storage_records import LicensingWizardDraft, StoredLicensingDocument
from core.licensing.trust_material import ReleaseTrustMaterial
from core.licensing.types import UseDeclaration
from core.plugins.protocols_database import DatabasePluginsProtocol
from features.licensing.entitlement_eligibility import (
    require_entitlement_declaration_eligibility,
)
from features.licensing.stored_entitlement_validation import (
    StoredEntitlementValidationDependencies,
    validate_stored_entitlement,
)


@dataclass(frozen=True, slots=True)
class LicensingAdministrationDependencies:
    policy: EditionLicensingPolicy
    repository: LicensingRepositoryProtocol
    wizard_repository: LicensingWizardRepositoryProtocol
    database_plugins: DatabasePluginsProtocol
    trust_material: ReleaseTrustMaterial

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LicensingAdministrationDependencies",
            database_plugins=self.database_plugins,
            policy=self.policy,
            repository=self.repository,
            trust_material=self.trust_material,
            wizard_repository=self.wizard_repository,
        )


class LicensingAdministrationOperations:
    def __init__(self, dependencies: LicensingAdministrationDependencies) -> None:
        self._deps = dependencies

    async def change_declaration(
        self,
        *,
        expected_revision: int,
        declaration: UseDeclaration,
        attestation_confirmed: bool,
        attestation_revision: str | None,
        actor_user_id: int,
        now_ms: int,
    ) -> LicensingWizardDraft:
        retire_active_entitlement = not self._deps.policy.product_access_required(declaration)
        active_document = await self._deps.repository.active_document()
        active_digest: str | None = None
        if retire_active_entitlement:
            if active_document is not None:
                active_digest = active_document.document_digest
        elif active_document is None:
            if self._deps.policy.edition != "soai-core":
                raise ValidationError("A valid licensing entitlement is required.")
        else:
            active_digest, payload, verified_time = await self._validated_active(
                active_document,
                now_ms,
            )
            require_entitlement_declaration_eligibility(
                payload,
                edition=self._deps.policy.edition,
                declaration=declaration,
                now_ms=now_ms,
                verified_time_high_water_ms=verified_time,
            )
        return await self._deps.wizard_repository.set_authenticated_declaration(
            edition=self._deps.policy.edition,
            expected_revision=expected_revision,
            declaration=declaration,
            attestation_confirmed=attestation_confirmed,
            attestation_revision=attestation_revision,
            expected_active_document_digest=active_digest,
            retire_active_entitlement=retire_active_entitlement,
            changed_at_ms=now_ms,
            actor_user_id=actor_user_id,
        )

    async def _validated_active(
        self,
        stored: StoredLicensingDocument,
        now_ms: int,
    ) -> tuple[str, ParsedEntitlementPayload, int]:
        validated = await validate_stored_entitlement(
            StoredEntitlementValidationDependencies(
                self._deps.policy,
                self._deps.repository,
                self._deps.database_plugins,
                self._deps.trust_material,
            ),
            stored,
            now_ms=now_ms,
        )
        return (
            stored.document_digest,
            validated.payload,
            validated.verified_time_high_water_ms,
        )


__all__ = (
    "LicensingAdministrationDependencies",
    "LicensingAdministrationOperations",
)
