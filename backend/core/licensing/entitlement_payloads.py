"""SoAI - Exact licensing entitlement payloads [backend/core/licensing/entitlement_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.errors.exceptions import ValidationError
from core.licensing.capabilities import (
    require_commercial_licensing_capabilities,
    require_licensing_capabilities,
)
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.governing_documents import GoverningDocument, parse_governing_documents
from core.licensing.identifiers import require_canonical_uuid4, require_licensing_identifier
from core.licensing.timestamps import parse_licensing_timestamp
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields

__all__ = ("ParsedEntitlementPayload", "parse_entitlement_payload")

_COMMON_FIELDS = frozenset(
    (
        "schema_version",
        "licensed_product_scope",
        "deployment_product",
        "entitlement_type",
        "instance_id",
        "deployment_id",
        "deployment_public_key",
        "issued_at",
        "effective_at",
        "validation_mode",
        "entitlement_generation",
        "governing_documents",
    )
)


@dataclass(frozen=True, slots=True)
class ParsedEntitlementPayload:
    entitlement_type: str
    licensed_product_scope: str
    deployment_product: str
    instance_id: str
    deployment_id: str
    deployment_public_key: bytes
    issued_at: datetime
    effective_at: datetime
    generation: int
    capabilities: tuple[str, ...]
    governing_documents: tuple[GoverningDocument, ...]
    values: JSONDict


def parse_entitlement_payload(
    value: JSONValue, signature_domain: JSONValue
) -> ParsedEntitlementPayload:
    payload = _require_object(value)
    entitlement_type = _require_string(payload.get("entitlement_type"), "entitlement_type")
    expected_domain = {
        "organization_evaluation": "soai-entitlement-evaluation-v1",
        "commercial_term": "soai-entitlement-commercial-term-v1",
        "commercial_continuity": "soai-entitlement-commercial-continuity-v1",
        "personal_os_perpetual": "soai-entitlement-personal-os-v1",
        "commercial_full_perpetual": "soai-deployment-binding-commercial-perpetual-v1",
    }.get(entitlement_type)
    if expected_domain is None or signature_domain != expected_domain:
        raise ValidationError("Licensing entitlement type and signature domain disagree.")
    require_exact_json_fields(
        payload,
        allowed_fields=_allowed_fields(entitlement_type),
        label="Entitlement payload",
    )
    if payload.get("schema_version") != 1:
        raise ValidationError("Licensing entitlement schema is invalid.")
    licensed_scope = _require_string(
        payload.get("licensed_product_scope"), "licensed_product_scope"
    )
    deployment_product = _require_string(payload.get("deployment_product"), "deployment_product")
    if licensed_scope not in {"soai_core", "soai_os", "soai_core_and_os"}:
        raise ValidationError("Licensing product scope is invalid.")
    if deployment_product not in {"soai_core", "soai_os"}:
        raise ValidationError("Licensing deployment product is invalid.")
    if licensed_scope == "soai_core" and deployment_product != "soai_core":
        raise ValidationError("Core scope cannot authorize an OS deployment.")
    if licensed_scope == "soai_os" and deployment_product != "soai_os":
        raise ValidationError("OS scope cannot authorize a Core deployment.")
    parsed = ParsedEntitlementPayload(
        entitlement_type,
        licensed_scope,
        deployment_product,
        require_canonical_uuid4(_require_string(payload.get("instance_id"), "instance_id")),
        require_licensing_identifier(payload.get("deployment_id"), label="Licensing deployment_id"),
        decode_licensing_base64url(
            _require_string(payload.get("deployment_public_key"), "deployment_public_key"),
            expected_bytes=32,
        ),
        parse_licensing_timestamp(payload.get("issued_at"), field="issued_at"),
        parse_licensing_timestamp(payload.get("effective_at"), field="effective_at"),
        _positive_integer(payload.get("entitlement_generation"), "entitlement_generation"),
        _capabilities(payload, entitlement_type),
        parse_governing_documents(payload.get("governing_documents")),
        payload,
    )
    _validate_type_specific(parsed)
    return parsed


def _allowed_fields(entitlement_type: str) -> frozenset[str]:
    if entitlement_type == "organization_evaluation":
        return _COMMON_FIELDS | frozenset(
            ("evaluation_id", "organization_id", "term_starts_at", "term_ends_at")
        )
    if entitlement_type == "commercial_term":
        return _paid_fields() | frozenset(
            (
                "term_id",
                "term_starts_at",
                "term_ends_at",
                "deployment_environment",
                "allowed_production_deployments",
                "allowed_non_production_deployments",
                "support_hours_included",
                "updates_included",
            )
        )
    if entitlement_type == "commercial_continuity":
        return _COMMON_FIELDS | frozenset(
            (
                "license_id",
                "previous_term_id",
                "previous_term_ends_at",
                "renewal_proof_reference",
                "deployment_environment",
                "allowed_production_deployments",
                "allowed_non_production_deployments",
                "continuity_starts_at",
                "continuity_ends_at",
            )
        )
    if entitlement_type == "personal_os_perpetual":
        return _paid_fields() | frozenset(("allowed_personal_deployments",))
    return _paid_fields() | frozenset(
        (
            "deployment_environment",
            "allowed_production_deployments",
            "allowed_non_production_deployments",
            "grant_certificate",
        )
    )


def _paid_fields() -> frozenset[str]:
    return _COMMON_FIELDS | frozenset(("license_id", "activation_id", "licensed_capabilities"))


def _capabilities(payload: JSONDict, entitlement_type: str) -> tuple[str, ...]:
    if entitlement_type in {"organization_evaluation", "commercial_continuity"}:
        if "licensed_capabilities" in payload:
            raise ValidationError("Entitlement capabilities are not permitted.")
        return ()
    return require_licensing_capabilities(payload.get("licensed_capabilities"))


def _validate_type_specific(parsed: ParsedEntitlementPayload) -> None:
    if parsed.effective_at > parsed.issued_at:
        raise ValidationError("Licensing effective time is invalid.")
    if parsed.entitlement_type == "organization_evaluation":
        _validate_evaluation(parsed)
        return
    if parsed.entitlement_type == "commercial_continuity":
        _validate_continuity(parsed)
        return
    payload = parsed.values
    require_licensing_identifier(payload.get("license_id"), label="Licensing license_id")
    require_licensing_identifier(payload.get("activation_id"), label="Licensing activation_id")
    if parsed.entitlement_type == "personal_os_perpetual":
        if (
            payload.get("validation_mode") != "local_only"
            or parsed.licensed_product_scope != "soai_os"
            or parsed.capabilities != ("personal_noncommercial",)
            or payload.get("allowed_personal_deployments") != 3
        ):
            raise ValidationError("Personal SoAI OS entitlement is contradictory.")
        return
    require_commercial_licensing_capabilities(parsed.capabilities)
    if parsed.entitlement_type == "commercial_term":
        _validate_commercial_term(parsed)
    elif (
        payload.get("validation_mode") != "local_only"
        or payload.get("deployment_environment") not in {"production", "non_production"}
        or not _positive_allowance(payload.get("allowed_production_deployments"))
        or not _positive_allowance(payload.get("allowed_non_production_deployments"))
    ):
        raise ValidationError("Commercial perpetual entitlement is contradictory.")


def _validate_evaluation(parsed: ParsedEntitlementPayload) -> None:
    payload = parsed.values
    start, end = _term_boundaries(payload)
    if (
        payload.get("validation_mode") != "local_only"
        or parsed.capabilities
        or parsed.effective_at != start
        or parsed.licensed_product_scope not in {"soai_core", "soai_os"}
    ):
        raise ValidationError("Organization evaluation entitlement is contradictory.")
    require_licensing_identifier(payload.get("evaluation_id"), label="Licensing evaluation_id")
    require_licensing_identifier(payload.get("organization_id"), label="Licensing organization_id")
    if start >= end:
        raise ValidationError("Evaluation term ordering is invalid.")


def _validate_commercial_term(parsed: ParsedEntitlementPayload) -> None:
    payload = parsed.values
    start, end = _term_boundaries(payload)
    fixed_contract = (
        payload.get("validation_mode"),
        parsed.effective_at,
        payload.get("allowed_production_deployments"),
        payload.get("allowed_non_production_deployments"),
        payload.get("updates_included"),
    ) == ("term_fixed", start, 3, 3, True)
    deployment_environment = payload.get("deployment_environment")
    support_hours = payload.get("support_hours_included")
    if (
        not fixed_contract
        or start >= end
        or deployment_environment not in {"production", "non_production"}
        or support_hours not in {1, 2, 4}
    ):
        raise ValidationError("Commercial term entitlement is contradictory.")
    require_licensing_identifier(payload.get("term_id"), label="Licensing term_id")


def _validate_continuity(parsed: ParsedEntitlementPayload) -> None:
    payload = parsed.values
    start = parse_licensing_timestamp(
        payload.get("continuity_starts_at"), field="continuity_starts_at"
    )
    end = parse_licensing_timestamp(payload.get("continuity_ends_at"), field="continuity_ends_at")
    previous_end = parse_licensing_timestamp(
        payload.get("previous_term_ends_at"), field="previous_term_ends_at"
    )
    fixed_contract = (
        payload.get("validation_mode"),
        parsed.effective_at,
        previous_end,
        payload.get("allowed_production_deployments"),
        payload.get("allowed_non_production_deployments"),
    ) == ("term_fixed", start, start, 3, 3)
    duration_valid = start < end and end - start <= timedelta(days=30)
    if (
        not fixed_contract
        or not duration_valid
        or payload.get("deployment_environment") not in {"production", "non_production"}
    ):
        raise ValidationError("Commercial continuity entitlement is contradictory.")
    require_licensing_identifier(payload.get("license_id"), label="Licensing license_id")
    require_licensing_identifier(
        payload.get("previous_term_id"), label="Licensing previous_term_id"
    )
    require_licensing_identifier(
        payload.get("renewal_proof_reference"), label="Licensing renewal proof"
    )


def _term_boundaries(payload: JSONDict) -> tuple[datetime, datetime]:
    return (
        parse_licensing_timestamp(payload.get("term_starts_at"), field="term_starts_at"),
        parse_licensing_timestamp(payload.get("term_ends_at"), field="term_ends_at"),
    )


def _positive_integer(value: JSONValue, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"Licensing {field} must be a positive integer.")
    return value


def _positive_allowance(value: JSONValue) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 1


def _require_string(value: JSONValue, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"Licensing {field} must be a string.")
    return value


def _require_object(value: JSONValue) -> JSONDict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValidationError("Licensing entitlement payload must be an object.")
    return value
