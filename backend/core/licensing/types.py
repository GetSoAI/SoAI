"""SoAI - Licensing V1 closed domain types [backend/core/licensing/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

__all__ = (
    "LicensingActivationInput",
    "LicensingStatus",
    "LicensingStatusFacts",
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

    type Edition = Literal["soai-core", "soai-os"]
    type LicensedProductScope = Literal["soai_core", "soai_os", "soai_core_and_os"]
    type UseDeclaration = Literal["personal", "organization_commercial"]
    type EntitlementType = Literal[
        "organization_evaluation",
        "commercial_term",
        "commercial_continuity",
        "personal_os_perpetual",
        "commercial_full_perpetual",
    ]
    type ValidationMode = Literal["local_only", "term_fixed"]
    type IntegrityFailure = Literal["invalid_signature", "invalid_binding", "invalid_contract"]
    type SignedLicensingState = Literal["suspended", "terminated"]
    type LicensingOperationState = Literal[
        "prepared",
        "sending",
        "outcome_unknown",
        "reconciling",
        "retry_wait",
        "succeeded",
        "failed",
        "cancelled",
    ]
    type LicensingState = Literal[
        "personal_declared",
        "evaluation_pending",
        "evaluation_active",
        "evaluation_expiring",
        "evaluation_expired",
        "personal_os_perpetual_active",
        "commercial_active",
        "commercial_expiring",
        "commercial_continuity",
        "commercial_expired",
        "commercial_perpetual_active",
        "suspended",
        "terminated",
        "invalid_signature",
        "invalid_binding",
        "invalid_contract",
        "clock_invalid",
    ]
else:
    Edition = str
    LicensedProductScope = str
    UseDeclaration = str
    EntitlementType = str
    ValidationMode = str
    IntegrityFailure = str
    SignedLicensingState = str
    LicensingOperationState = str
    LicensingState = str


@dataclass(frozen=True, slots=True)
class LicensingActivationInput:
    draft_revision: int
    activation_source: str
    pending_evaluation_id: str | None
    activation_credential: str | None
    deployment_environment: str | None
    legal_acceptances: list[JSONValue]
    now_ms: int


@dataclass(frozen=True, slots=True)
class LicensingStatusFacts:
    edition: Edition
    license_accepted: bool
    declaration: UseDeclaration | None
    entitlement_type: EntitlementType | None
    validation_mode: ValidationMode | None
    now_ms: int
    verified_time_high_water_ms: int
    effective_at_ms: int | None
    term_starts_at_ms: int | None
    term_ends_at_ms: int | None
    continuity_starts_at_ms: int | None
    continuity_ends_at_ms: int | None
    operation_state: LicensingOperationState | None
    integrity_failure: IntegrityFailure | None
    signed_status: SignedLicensingState | None
    declaration_eligible: bool


@dataclass(frozen=True, slots=True)
class LicensingStatus:
    state: LicensingState
    requires_repair_plane: bool
