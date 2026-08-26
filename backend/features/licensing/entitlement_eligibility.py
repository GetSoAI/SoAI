"""SoAI - Declaration-specific entitlement eligibility [backend/features/licensing/entitlement_eligibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.licensing.admission import LicensingOperationClass, resolve_licensing_admission
from core.licensing.entitlement_payloads import ParsedEntitlementPayload
from core.licensing.status_resolution import resolve_licensing_status
from core.licensing.types import Edition, UseDeclaration
from features.licensing.runtime_facts import facts_from_payload


def require_entitlement_declaration_eligibility(
    payload: ParsedEntitlementPayload,
    *,
    edition: Edition,
    declaration: UseDeclaration,
    now_ms: int,
    verified_time_high_water_ms: int,
) -> None:
    if not entitlement_permits_declaration(payload, declaration):
        raise ValidationError("Licensing entitlement does not permit the declaration.")
    facts = facts_from_payload(
        payload,
        edition=edition,
        license_accepted=True,
        use_declaration=declaration,
        now_ms=now_ms,
        operation_state=None,
        verified_time_high_water_ms=verified_time_high_water_ms,
        signed_status=None,
        declaration_eligible=True,
    )
    status = resolve_licensing_status(facts)
    if not resolve_licensing_admission(
        status.state,
        LicensingOperationClass.ORDINARY,
    ).allowed:
        raise ValidationError("Licensing entitlement is not currently usable.")


def entitlement_permits_declaration(
    payload: ParsedEntitlementPayload,
    declaration: UseDeclaration,
) -> bool:
    if declaration == "organization_commercial":
        return payload.entitlement_type in {
            "organization_evaluation",
            "commercial_term",
            "commercial_full_perpetual",
        }
    return (
        payload.entitlement_type
        in {"personal_os_perpetual", "commercial_term", "commercial_full_perpetual"}
        and "personal_noncommercial" in payload.capabilities
    )


__all__ = (
    "entitlement_permits_declaration",
    "require_entitlement_declaration_eligibility",
)
