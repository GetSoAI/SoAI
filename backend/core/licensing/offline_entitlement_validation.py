"""SoAI - Root-signed final offline entitlement validation [backend/core/licensing/offline_entitlement_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import (
    canonicalize_licensing_json,
    parse_canonical_licensing_document,
)
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.entitlement_payloads import ParsedEntitlementPayload, parse_entitlement_payload
from core.licensing.entitlement_validation import build_safe_entitlement_summary
from core.licensing.errors import LicensingIntegrityError
from core.licensing.grant_certificate import validate_full_perpetual_grant_certificate
from core.licensing.identifiers import require_canonical_uuid4
from core.licensing.trust import IssuerAuthorizationCatalog, issuer_key_identity
from core.licensing.types import Edition
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields

OFFLINE_ENTITLEMENT_SIGNATURE_DOMAIN = "soai-offline-entitlement-v1"
_ENVELOPE_FIELDS = frozenset(
    (
        "schema_version",
        "payload",
        "allocation_issuer_authorization",
        "root_key_id",
        "signature_domain",
        "signature",
    )
)
_COMMON_PAYLOAD_FIELDS = frozenset(
    (
        "schema_version",
        "document_type",
        "allocation_id",
        "license_id",
        "activation_id",
        "entitlement_type",
        "licensed_product_scope",
        "deployment_product",
        "licensed_capabilities",
        "instance_id",
        "deployment_id",
        "deployment_public_key",
        "issued_at",
        "effective_at",
        "entitlement_generation",
        "validation_mode",
        "governing_documents",
        "customer_request_digest",
    )
)


@dataclass(frozen=True, slots=True)
class OfflineEntitlementBinding:
    edition: Edition
    instance_id: str
    deployment_public_key: bytes
    customer_request_digest: str
    current_deployment_id: str | None
    current_generation: int | None
    current_document: bytes | None

    def __post_init__(self) -> None:
        if self.edition not in {"soai-core", "soai-os"}:
            raise ValidationError("Offline entitlement edition binding is invalid.")
        require_canonical_uuid4(self.instance_id)
        if len(self.deployment_public_key) != 32:
            raise ValidationError("Offline entitlement deployment key binding is invalid.")
        if re.fullmatch(r"sha256:[a-f0-9]{64}", self.customer_request_digest) is None:
            raise ValidationError("Offline entitlement request digest binding is invalid.")
        if (self.current_generation is None) != (self.current_deployment_id is None):
            raise ValidationError("Offline entitlement generation lineage binding is incomplete.")
        if self.current_generation is not None and self.current_generation < 1:
            raise ValidationError("Offline entitlement generation binding is invalid.")


@dataclass(frozen=True, slots=True)
class ValidatedOfflineEntitlement:
    canonical_document: bytes
    document_digest: str
    root_snapshot: bytes
    entitlement_type: str
    license_id: str
    allocation_id: str
    deployment_id: str
    generation: int
    summary: JSONDict
    payload: ParsedEntitlementPayload


def validate_offline_entitlement(
    raw_document: bytes,
    root_public_key_bytes: bytes,
    binding: OfflineEntitlementBinding,
) -> ValidatedOfflineEntitlement:
    envelope = _require_object(parse_canonical_licensing_document(raw_document), "certificate")
    require_exact_json_fields(
        envelope,
        allowed_fields=_ENVELOPE_FIELDS,
        label="Offline entitlement certificate",
    )
    if (
        envelope.get("schema_version") != 1
        or envelope.get("signature_domain") != OFFLINE_ENTITLEMENT_SIGNATURE_DOMAIN
    ):
        raise ValidationError("Offline entitlement certificate contract is invalid.")
    root_public_key = _root_public_key(root_public_key_bytes)
    if envelope.get("root_key_id") != issuer_key_identity(root_public_key_bytes):
        raise LicensingIntegrityError.for_failure(
            "invalid_signature", "Offline entitlement root identity is invalid."
        )
    payload = _require_object(envelope.get("payload"), "payload")
    parsed, license_id, allocation_id = parse_offline_entitlement_payload(payload)
    _validate_binding(parsed, payload, binding)
    signature_text = envelope.get("signature")
    if not isinstance(signature_text, str):
        raise ValidationError("Offline entitlement signature is invalid.")
    signed_values = dict(envelope)
    del signed_values["signature"]
    try:
        root_public_key.verify(
            decode_licensing_base64url(signature_text, expected_bytes=64),
            b"".join(
                (
                    OFFLINE_ENTITLEMENT_SIGNATURE_DOMAIN.encode("ascii"),
                    b"\0",
                    canonicalize_licensing_json(signed_values),
                )
            ),
        )
    except InvalidSignature as exception:
        raise LicensingIntegrityError.for_failure(
            "invalid_signature", "Offline entitlement signature is invalid."
        ) from exception
    authorization_bytes = _validate_allocation_authorization(
        root_public_key,
        envelope.get("allocation_issuer_authorization"),
        parsed,
    )
    if parsed.entitlement_type == "commercial_full_perpetual":
        validate_full_perpetual_grant_certificate(
            parsed.values.get("grant_certificate"),
            IssuerAuthorizationCatalog(root_public_key, {}),
            parsed,
        )
    _validate_generation(raw_document, parsed, binding)
    summary = build_safe_entitlement_summary(parsed)
    summary["validation_mode"] = parsed.values["validation_mode"]
    return ValidatedOfflineEntitlement(
        raw_document,
        f"sha256:{hashlib.sha256(raw_document).hexdigest()}",
        authorization_bytes,
        parsed.entitlement_type,
        license_id,
        allocation_id,
        parsed.deployment_id,
        parsed.generation,
        summary,
        parsed,
    )


def parse_offline_entitlement_payload(
    payload: JSONDict,
) -> tuple[ParsedEntitlementPayload, str, str]:
    entitlement_type_value = payload.get("entitlement_type")
    entitlement_type = entitlement_type_value if isinstance(entitlement_type_value, str) else ""
    allowed_fields = _COMMON_PAYLOAD_FIELDS | _type_fields(entitlement_type)
    require_exact_json_fields(payload, allowed_fields=allowed_fields, label="Offline entitlement")
    if payload.get("schema_version") != 1 or payload.get("document_type") != "offline_entitlement":
        raise ValidationError("Offline entitlement payload contract is invalid.")
    license_id = _require_identity(payload.get("license_id"))
    allocation_id = _require_identity(payload.get("allocation_id"))
    _require_identity(payload.get("activation_id"))
    normalized = dict(payload)
    del normalized["document_type"]
    del normalized["allocation_id"]
    del normalized["customer_request_digest"]
    signature_domain = {
        "commercial_term": "soai-entitlement-commercial-term-v1",
        "personal_os_perpetual": "soai-entitlement-personal-os-v1",
        "commercial_full_perpetual": "soai-deployment-binding-commercial-perpetual-v1",
    }.get(entitlement_type)
    if signature_domain is None:
        raise ValidationError("Offline entitlement type is invalid.")
    return parse_entitlement_payload(normalized, signature_domain), license_id, allocation_id


def _type_fields(entitlement_type: JSONValue) -> frozenset[str]:
    if entitlement_type == "personal_os_perpetual":
        return frozenset(("allowed_personal_deployments",))
    if entitlement_type == "commercial_term":
        return frozenset(
            (
                "deployment_environment",
                "allowed_production_deployments",
                "allowed_non_production_deployments",
                "term_id",
                "term_starts_at",
                "term_ends_at",
                "support_hours_included",
                "updates_included",
            )
        )
    if entitlement_type == "commercial_full_perpetual":
        return frozenset(
            (
                "deployment_environment",
                "allowed_production_deployments",
                "allowed_non_production_deployments",
                "grant_certificate",
            )
        )
    raise ValidationError("Offline entitlement type is invalid.")


def _validate_allocation_authorization(
    root_public_key: Ed25519PublicKey,
    value: JSONValue,
    payload: ParsedEntitlementPayload,
) -> bytes:
    snapshot = canonicalize_licensing_json(value)
    authorization = _require_object(value, "allocation issuer authorization")
    IssuerAuthorizationCatalog(root_public_key, {}).resolve_snapshot(
        snapshot,
        issuer_key_id=authorization.get("issuer_key_id"),
        signature_domain="soai-offline-allocation-request-v1",
        entitlement_type="offline_allocation_request",
        licensed_product_scope=payload.licensed_product_scope,
        issued_at=payload.issued_at,
        allowed_personal_deployments=_personal_allowance(payload),
    )
    return snapshot


def _validate_binding(
    parsed: ParsedEntitlementPayload,
    payload: JSONDict,
    binding: OfflineEntitlementBinding,
) -> None:
    expected_scope = "soai_core" if binding.edition == "soai-core" else "soai_os"
    if (
        parsed.licensed_product_scope not in {expected_scope, "soai_core_and_os"}
        or parsed.instance_id != binding.instance_id
        or not hmac.compare_digest(parsed.deployment_public_key, binding.deployment_public_key)
        or payload.get("customer_request_digest") != binding.customer_request_digest
    ):
        raise LicensingIntegrityError.for_failure(
            "invalid_binding", "Offline entitlement binding is invalid."
        )


def _validate_generation(
    raw_document: bytes,
    parsed: ParsedEntitlementPayload,
    binding: OfflineEntitlementBinding,
) -> None:
    if (
        binding.current_generation is not None
        and binding.current_deployment_id == parsed.deployment_id
        and parsed.generation <= binding.current_generation
        and (
            binding.current_document is None
            or not hmac.compare_digest(raw_document, binding.current_document)
        )
    ):
        raise ValidationError("Offline entitlement generation does not advance.")


def _root_public_key(value: bytes) -> Ed25519PublicKey:
    if len(value) != 32:
        raise ValidationError("Offline entitlement root key is invalid.")
    try:
        return Ed25519PublicKey.from_public_bytes(value)
    except ValueError as exception:
        raise ValidationError("Offline entitlement root key is invalid.") from exception


def _require_identity(value: JSONValue) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"(?:off|lic|act)_[A-Za-z0-9_-]{22}", value) is None
    ):
        raise ValidationError("Offline entitlement identity is invalid.")
    return value


def _require_object(value: JSONValue, label: str) -> JSONDict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValidationError(f"Offline entitlement {label} must be an object.")
    return value


def _personal_allowance(payload: ParsedEntitlementPayload) -> int | None:
    value = payload.values.get("allowed_personal_deployments")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = (
    "OFFLINE_ENTITLEMENT_SIGNATURE_DOMAIN",
    "OfflineEntitlementBinding",
    "ValidatedOfflineEntitlement",
    "parse_offline_entitlement_payload",
    "validate_offline_entitlement",
)
