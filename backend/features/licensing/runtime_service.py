"""SoAI - Derived licensing status and admission owner [backend/features/licensing/runtime_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ConcurrencyError, SecurityError, StateError, ValidationError
from core.licensing.admission import (
    LicensingAdmissionDecision,
    LicensingOperationClass,
    resolve_licensing_admission,
)
from core.licensing.errors import LicensingIntegrityError
from core.licensing.license_acceptance import require_current_license_acceptance
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import (
    LicensingRepairPlaneCoordinatorProtocol,
    LicensingRepositoryProtocol,
    LicensingWizardRepositoryProtocol,
)
from core.licensing.status_resolution import (
    resolve_effective_licensing_status,
    resolve_licensing_status,
)
from core.licensing.storage_records import StoredLicensingDocument
from core.licensing.trust_material import ReleaseTrustMaterial
from core.licensing.types import (
    IntegrityFailure,
    LicensingOperationState,
    LicensingStatus,
    LicensingStatusFacts,
)
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.licensing.entitlement_eligibility import (
    entitlement_permits_declaration,
    require_entitlement_declaration_eligibility,
)
from features.licensing.runtime_facts import (
    build_administrative_entitlement_summary,
    build_runtime_status_payload,
    declaration,
    empty_facts,
    facts_from_payload,
    parse_operation_state,
)
from features.licensing.stored_entitlement_validation import (
    StoredEntitlementValidationDependencies,
    validate_stored_entitlement,
)
from features.licensing.stored_status_validation import validate_stored_status


@dataclass(frozen=True, slots=True)
class LicensingRuntimeServiceDependencies:
    policy: EditionLicensingPolicy
    repository: LicensingRepositoryProtocol
    wizard_repository: LicensingWizardRepositoryProtocol
    database_plugins: DatabasePluginsProtocol
    trust_material: ReleaseTrustMaterial
    controlling_license_fingerprint: str
    repair_plane_coordinator: LicensingRepairPlaneCoordinatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LicensingRuntimeServiceDependencies",
            controlling_license_fingerprint=self.controlling_license_fingerprint,
            database_plugins=self.database_plugins,
            policy=self.policy,
            repair_plane_coordinator=self.repair_plane_coordinator,
            repository=self.repository,
            trust_material=self.trust_material,
            wizard_repository=self.wizard_repository,
        )
        if (
            re.fullmatch(
                r"sha256:[a-f0-9]{64}",
                self.controlling_license_fingerprint,
            )
            is None
        ):
            raise ValidationError("Controlling license fingerprint is invalid.")


class LicensingRuntimeService:
    def __init__(self, deps: LicensingRuntimeServiceDependencies) -> None:
        self._deps = deps

    @property
    def controlling_license_fingerprint(self) -> str:
        return self._deps.controlling_license_fingerprint

    async def resolved_status(self) -> LicensingStatus:
        return resolve_effective_licensing_status(
            await self.dynamic_status(),
            startup_repair_plane=(self._deps.repair_plane_coordinator.startup_repair_plane_active),
        )

    async def dynamic_status(self) -> LicensingStatus:
        facts, _summary, _administrative_summary = await self._resolve()
        return resolve_licensing_status(facts)

    async def public_status(self) -> JSONDict:
        facts, summary, _administrative_summary = await self._resolve()
        return build_runtime_status_payload(
            edition=self._deps.policy.edition,
            facts=facts,
            status=resolve_licensing_status(facts),
            startup_repair_plane=(self._deps.repair_plane_coordinator.startup_repair_plane_active),
            entitlement=summary,
        )

    async def administrative_status(self) -> JSONDict:
        facts, _summary, administrative_summary = await self._resolve()
        status = resolve_licensing_status(facts)
        await self._deps.repair_plane_coordinator.reconcile(status.requires_repair_plane)
        return build_runtime_status_payload(
            edition=self._deps.policy.edition,
            facts=facts,
            status=status,
            startup_repair_plane=(self._deps.repair_plane_coordinator.startup_repair_plane_active),
            entitlement=administrative_summary,
        )

    async def admission(
        self,
        operation_class: LicensingOperationClass,
    ) -> LicensingAdmissionDecision:
        status = await self.resolved_status()
        return resolve_licensing_admission(
            status.state,
            operation_class,
            requires_repair_plane=status.requires_repair_plane,
        )

    async def validate_pending_completion(
        self,
        *,
        expected_revision: int,
        now_ms: int,
    ) -> str | None:
        draft = await self._deps.wizard_repository.read_wizard_draft(self._deps.policy.edition)
        if draft.get("revision") != expected_revision:
            raise ConcurrencyError("Licensing wizard state changed before completion.")
        require_current_license_acceptance(
            draft,
            self._deps.controlling_license_fingerprint,
        )
        selected_declaration = declaration(draft.get("declaration"))
        if selected_declaration is None:
            raise ValidationError("A use declaration is required before completion.")
        if not self._deps.policy.product_access_required(selected_declaration):
            return None
        pending = await self._deps.repository.pending_document()
        if pending is None:
            raise ValidationError("A valid product entitlement is required before completion.")
        validated = await validate_stored_entitlement(
            StoredEntitlementValidationDependencies(
                self._deps.policy,
                self._deps.repository,
                self._deps.database_plugins,
                self._deps.trust_material,
            ),
            pending,
            now_ms=now_ms,
        )
        require_entitlement_declaration_eligibility(
            validated.payload,
            edition=self._deps.policy.edition,
            declaration=selected_declaration,
            now_ms=now_ms,
            verified_time_high_water_ms=validated.verified_time_high_water_ms,
        )
        return pending.document_digest

    async def _resolve(
        self,
    ) -> tuple[LicensingStatusFacts, JSONDict | None, JSONDict | None]:
        now_ms = epoch_ms()
        resolved_declaration = None
        license_accepted = False
        operation_state: LicensingOperationState | None = None
        active: StoredLicensingDocument | None = None
        active_status: StoredLicensingDocument | None = None
        try:
            draft = await self._deps.wizard_repository.read_wizard_draft(self._deps.policy.edition)
            resolved_declaration = declaration(draft.get("declaration"))
            license_accepted = (
                draft.get("accepted_license_fingerprint")
                == self._deps.controlling_license_fingerprint
            )
            active = await self._deps.repository.active_document()
            active_status = await self._deps.repository.active_status_document()
            latest_operation = await self._deps.repository.latest_operation()
            operation_state = (
                None
                if latest_operation is None
                else parse_operation_state(latest_operation.get("state"))
            )
        except SecurityError:
            stored_state_failure: IntegrityFailure | None = "invalid_binding"
        except (StateError, ValidationError):
            stored_state_failure = "invalid_contract"
        else:
            stored_state_failure = None
        if stored_state_failure is not None:
            return (
                empty_facts(
                    edition=self._deps.policy.edition,
                    license_accepted=license_accepted,
                    use_declaration=resolved_declaration,
                    now_ms=now_ms,
                    operation_state=operation_state,
                    integrity_failure=stored_state_failure,
                ),
                None,
                None,
            )
        if self._deps.trust_material.catalog is None:
            return (
                empty_facts(
                    edition=self._deps.policy.edition,
                    license_accepted=license_accepted,
                    use_declaration=resolved_declaration,
                    now_ms=now_ms,
                    operation_state=operation_state,
                    integrity_failure="invalid_contract",
                ),
                None,
                None,
            )
        if active is None:
            integrity_failure: IntegrityFailure | None = (
                "invalid_contract" if active_status is not None else None
            )
            return (
                empty_facts(
                    edition=self._deps.policy.edition,
                    license_accepted=license_accepted,
                    use_declaration=resolved_declaration,
                    now_ms=now_ms,
                    operation_state=operation_state,
                    integrity_failure=integrity_failure,
                ),
                None,
                None,
            )
        if active.document_type not in {"entitlement", "offline_entitlement"}:
            return (
                empty_facts(
                    edition=self._deps.policy.edition,
                    license_accepted=license_accepted,
                    use_declaration=resolved_declaration,
                    now_ms=now_ms,
                    operation_state=operation_state,
                    integrity_failure="invalid_contract",
                ),
                None,
                None,
            )
        try:
            validated = await validate_stored_entitlement(
                StoredEntitlementValidationDependencies(
                    self._deps.policy,
                    self._deps.repository,
                    self._deps.database_plugins,
                    self._deps.trust_material,
                ),
                active,
                now_ms=now_ms,
            )
            parsed = validated.payload
            validated_status = await validate_stored_status(
                self._deps.repository,
                active,
                active_status,
                validated,
                now_ms=now_ms,
            )
            return (
                facts_from_payload(
                    parsed,
                    edition=self._deps.policy.edition,
                    license_accepted=license_accepted,
                    use_declaration=resolved_declaration,
                    now_ms=now_ms,
                    operation_state=operation_state,
                    verified_time_high_water_ms=(validated_status.verified_time_high_water_ms),
                    signed_status=validated_status.signed_state,
                    declaration_eligible=(
                        resolved_declaration is not None
                        and entitlement_permits_declaration(parsed, resolved_declaration)
                    ),
                ),
                validated.safe_summary,
                build_administrative_entitlement_summary(
                    parsed,
                    online_maintenance_available=(active.document_type == "entitlement"),
                ),
            )
        except LicensingIntegrityError as exception:
            failure = exception.failure
        except SecurityError:
            failure = "invalid_binding"
        except (StateError, ValidationError):
            failure = "invalid_contract"
        return (
            empty_facts(
                edition=self._deps.policy.edition,
                license_accepted=license_accepted,
                use_declaration=resolved_declaration,
                now_ms=now_ms,
                operation_state=operation_state,
                integrity_failure=failure,
            ),
            None,
            None,
        )


__all__ = ("LicensingRuntimeService", "LicensingRuntimeServiceDependencies")
