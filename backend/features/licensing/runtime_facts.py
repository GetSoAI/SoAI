"""SoAI - Licensing runtime fact projection [backend/features/licensing/runtime_facts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import parse_canonical_licensing_document
from core.licensing.entitlement_payloads import ParsedEntitlementPayload, parse_entitlement_payload
from core.licensing.status_resolution import resolve_effective_licensing_status
from core.licensing.timestamps import parse_licensing_timestamp
from core.licensing.types import (
    Edition,
    EntitlementType,
    IntegrityFailure,
    LicensingOperationState,
    LicensingStatus,
    LicensingStatusFacts,
    SignedLicensingState,
    UseDeclaration,
    ValidationMode,
)
from core.types.json import JSONDict, JSONValue


def build_runtime_status_payload(
    *,
    edition: Edition,
    facts: LicensingStatusFacts,
    status: LicensingStatus,
    startup_repair_plane: bool,
    entitlement: JSONDict | None,
) -> JSONDict:
    effective_status = resolve_effective_licensing_status(
        status,
        startup_repair_plane=startup_repair_plane,
    )
    return {
        "schema_version": 1,
        "edition": edition,
        "state": effective_status.state,
        "requires_repair_plane": effective_status.requires_repair_plane,
        "declaration": facts.declaration,
        "entitlement": entitlement,
    }


def parse_stored_entitlement(raw_document: bytes) -> ParsedEntitlementPayload:
    envelope = parse_canonical_licensing_document(raw_document)
    if not isinstance(envelope, dict):
        raise ValidationError("Stored licensing entitlement envelope is invalid.")
    return parse_entitlement_payload(envelope.get("payload"), envelope.get("signature_domain"))


def facts_from_payload(
    payload: ParsedEntitlementPayload,
    *,
    edition: Edition,
    license_accepted: bool,
    use_declaration: UseDeclaration | None,
    now_ms: int,
    operation_state: LicensingOperationState | None,
    verified_time_high_water_ms: int,
    signed_status: str | None,
    declaration_eligible: bool,
) -> LicensingStatusFacts:
    values = payload.values
    return LicensingStatusFacts(
        edition=edition,
        license_accepted=license_accepted,
        declaration=use_declaration,
        entitlement_type=_entitlement_type(payload.entitlement_type),
        validation_mode=_validation_mode(values.get("validation_mode")),
        now_ms=now_ms,
        verified_time_high_water_ms=verified_time_high_water_ms,
        effective_at_ms=int(payload.effective_at.timestamp() * 1000),
        term_starts_at_ms=_timestamp_ms(values.get("term_starts_at")),
        term_ends_at_ms=_timestamp_ms(values.get("term_ends_at")),
        continuity_starts_at_ms=_timestamp_ms(values.get("continuity_starts_at")),
        continuity_ends_at_ms=_timestamp_ms(values.get("continuity_ends_at")),
        operation_state=operation_state,
        integrity_failure=None,
        signed_status=_signed_status(signed_status),
        declaration_eligible=declaration_eligible,
    )


def build_administrative_entitlement_summary(
    payload: ParsedEntitlementPayload,
    *,
    online_maintenance_available: bool,
) -> JSONDict:
    values = payload.values
    return {
        "entitlement_type": payload.entitlement_type,
        "licensed_product_scope": payload.licensed_product_scope,
        "deployment_product": payload.deployment_product,
        "validation_mode": values.get("validation_mode"),
        "licensed_capabilities": list(payload.capabilities),
        "deployment_id": payload.deployment_id,
        "entitlement_generation": payload.generation,
        "deployment_environment": values.get("deployment_environment"),
        "allowed_personal_deployments": values.get("allowed_personal_deployments"),
        "allowed_production_deployments": values.get("allowed_production_deployments"),
        "allowed_non_production_deployments": values.get("allowed_non_production_deployments"),
        "support_hours_included": values.get("support_hours_included"),
        "effective_at": values.get("effective_at"),
        "term_starts_at": values.get("term_starts_at"),
        "term_ends_at": values.get("term_ends_at"),
        "continuity_starts_at": values.get("continuity_starts_at"),
        "continuity_ends_at": values.get("continuity_ends_at"),
        "perpetual": payload.entitlement_type
        in {"personal_os_perpetual", "commercial_full_perpetual"},
        "online_maintenance_available": online_maintenance_available,
    }


def empty_facts(
    *,
    edition: Edition,
    license_accepted: bool,
    use_declaration: UseDeclaration | None,
    now_ms: int,
    operation_state: LicensingOperationState | None,
    integrity_failure: IntegrityFailure | None,
) -> LicensingStatusFacts:
    return LicensingStatusFacts(
        edition=edition,
        license_accepted=license_accepted,
        declaration=use_declaration,
        entitlement_type=None,
        validation_mode=None,
        now_ms=now_ms,
        verified_time_high_water_ms=now_ms,
        effective_at_ms=None,
        term_starts_at_ms=None,
        term_ends_at_ms=None,
        continuity_starts_at_ms=None,
        continuity_ends_at_ms=None,
        operation_state=operation_state,
        integrity_failure=integrity_failure,
        signed_status=None,
        declaration_eligible=True,
    )


def declaration(value: JSONValue) -> UseDeclaration | None:
    if value is None:
        return None
    if value == "personal":
        return "personal"
    if value == "organization_commercial":
        return "organization_commercial"
    raise ValidationError("Stored licensing declaration is invalid.")


def parse_operation_state(value: JSONValue) -> LicensingOperationState:
    if value == "prepared":
        return "prepared"
    if value == "sending":
        return "sending"
    if value == "outcome_unknown":
        return "outcome_unknown"
    if value == "reconciling":
        return "reconciling"
    if value == "retry_wait":
        return "retry_wait"
    if value == "succeeded":
        return "succeeded"
    if value == "failed":
        return "failed"
    if value == "cancelled":
        return "cancelled"
    raise ValidationError("Stored licensing operation state is invalid.")


def _entitlement_type(value: str) -> EntitlementType:
    if value == "organization_evaluation":
        return "organization_evaluation"
    if value == "commercial_term":
        return "commercial_term"
    if value == "commercial_continuity":
        return "commercial_continuity"
    if value == "personal_os_perpetual":
        return "personal_os_perpetual"
    if value == "commercial_full_perpetual":
        return "commercial_full_perpetual"
    raise ValidationError("Stored licensing entitlement type is invalid.")


def _validation_mode(value: JSONValue) -> ValidationMode:
    if value == "term_fixed":
        return "term_fixed"
    if value == "local_only":
        return "local_only"
    raise ValidationError("Stored licensing validation mode is invalid.")


def _signed_status(value: str | None) -> SignedLicensingState | None:
    if value is None:
        return value
    if value == "suspended":
        return "suspended"
    if value == "terminated":
        return "terminated"
    raise ValidationError("Stored signed licensing status is invalid.")


def _timestamp_ms(value: JSONValue) -> int | None:
    if value is None:
        return None
    return int(parse_licensing_timestamp(value, field="licensing boundary").timestamp() * 1000)


__all__ = (
    "build_administrative_entitlement_summary",
    "build_runtime_status_payload",
    "declaration",
    "empty_facts",
    "facts_from_payload",
    "parse_operation_state",
    "parse_stored_entitlement",
)
