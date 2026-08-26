"""SoAI - Offline allocation request validation [backend/core/licensing/offline_allocation_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import (
    canonicalize_licensing_json,
    parse_canonical_licensing_document,
)
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.entitlement_payloads import ParsedEntitlementPayload
from core.licensing.offline_entitlement_validation import parse_offline_entitlement_payload
from core.licensing.trust import IssuerAuthorizationCatalog
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields

OFFLINE_ALLOCATION_SIGNATURE_DOMAIN = "soai-offline-allocation-request-v1"
_ENVELOPE_FIELDS = frozenset(
    (
        "schema_version",
        "payload",
        "issuer_key_id",
        "issuer_authorization",
        "signature_domain",
        "signature",
    )
)


@dataclass(frozen=True, slots=True)
class ValidatedOfflineAllocation:
    envelope: JSONDict
    payload: JSONDict
    authorization: JSONDict
    parsed_payload: ParsedEntitlementPayload


def validate_offline_allocation(
    raw_document: bytes,
    root_public_key_bytes: bytes,
) -> ValidatedOfflineAllocation:
    envelope = _require_object(
        parse_canonical_licensing_document(raw_document),
        "allocation envelope",
    )
    require_exact_json_fields(
        envelope,
        allowed_fields=_ENVELOPE_FIELDS,
        label="Offline allocation envelope",
    )
    if (
        envelope.get("schema_version") != 1
        or envelope.get("signature_domain") != OFFLINE_ALLOCATION_SIGNATURE_DOMAIN
    ):
        raise ValidationError("Offline allocation envelope contract is invalid.")
    payload = _require_object(envelope.get("payload"), "allocation payload")
    parsed, _license_id, _allocation_id = parse_offline_entitlement_payload(payload)
    authorization_value = envelope.get("issuer_authorization")
    authorization = _require_object(authorization_value, "issuer authorization")
    catalog = IssuerAuthorizationCatalog(_root_public_key(root_public_key_bytes), {})
    resolved = catalog.resolve_snapshot(
        canonicalize_licensing_json(authorization),
        issuer_key_id=envelope.get("issuer_key_id"),
        signature_domain=OFFLINE_ALLOCATION_SIGNATURE_DOMAIN,
        entitlement_type="offline_allocation_request",
        licensed_product_scope=parsed.licensed_product_scope,
        issued_at=parsed.issued_at,
        allowed_personal_deployments=_personal_allowance(parsed),
    )
    signature = envelope.get("signature")
    if not isinstance(signature, str):
        raise ValidationError("Offline allocation signature is invalid.")
    try:
        Ed25519PublicKey.from_public_bytes(resolved.public_key).verify(
            decode_licensing_base64url(signature, expected_bytes=64),
            OFFLINE_ALLOCATION_SIGNATURE_DOMAIN.encode("ascii")
            + b"\0"
            + canonicalize_licensing_json(payload),
        )
    except InvalidSignature as exception:
        raise ValidationError("Offline allocation signature is invalid.") from exception
    return ValidatedOfflineAllocation(envelope, payload, authorization, parsed)


def _root_public_key(value: bytes) -> Ed25519PublicKey:
    if len(value) != 32:
        raise ValidationError("Offline allocation root key is invalid.")
    try:
        return Ed25519PublicKey.from_public_bytes(value)
    except ValueError as exception:
        raise ValidationError("Offline allocation root key is invalid.") from exception


def _require_object(value: JSONValue, label: str) -> JSONDict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValidationError(f"Offline {label} must be an object.")
    return value


def _personal_allowance(payload: ParsedEntitlementPayload) -> int | None:
    value = payload.values.get("allowed_personal_deployments")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = (
    "OFFLINE_ALLOCATION_SIGNATURE_DOMAIN",
    "ValidatedOfflineAllocation",
    "validate_offline_allocation",
)
