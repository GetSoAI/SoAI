"""SoAI - Signed licensing entitlement validation [backend/core/licensing/entitlement_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import (
    canonicalize_licensing_json,
    parse_canonical_licensing_document,
)
from core.licensing.constants import SIGNED_LICENSING_ENVELOPE_FIELDS
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.entitlement_payloads import ParsedEntitlementPayload, parse_entitlement_payload
from core.licensing.errors import LicensingIntegrityError
from core.licensing.grant_certificate import validate_full_perpetual_grant_certificate
from core.licensing.identifiers import require_canonical_uuid4
from core.licensing.trust import IssuerAuthorizationCatalog
from core.licensing.types import Edition
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields


@dataclass(frozen=True, slots=True)
class EntitlementBinding:
    edition: Edition
    instance_id: str
    deployment_public_key: bytes
    current_deployment_id: str | None
    current_generation: int | None
    current_document: bytes | None

    def __post_init__(self) -> None:
        if self.edition not in {"soai-core", "soai-os"}:
            raise ValidationError("Licensing entitlement edition binding is invalid.")
        require_canonical_uuid4(self.instance_id)
        if len(self.deployment_public_key) != 32:
            raise ValidationError("Licensing deployment public key binding is invalid.")
        if (self.current_generation is None) != (self.current_deployment_id is None):
            raise ValidationError("Licensing generation lineage binding is incomplete.")
        if self.current_generation is not None and self.current_generation < 1:
            raise ValidationError("Licensing generation binding is invalid.")


@dataclass(frozen=True, slots=True)
class ValidatedEntitlement:
    canonical_document: bytes
    document_digest: str
    authorization_snapshot: bytes
    entitlement_type: str
    licensed_product_scope: str
    instance_id: str
    deployment_id: str
    generation: int
    summary: JSONDict


def validate_entitlement(
    raw_document: bytes,
    trust_catalog: IssuerAuthorizationCatalog,
    binding: EntitlementBinding,
    authorization_snapshot: bytes | None = None,
) -> ValidatedEntitlement:
    parsed = parse_canonical_licensing_document(raw_document)
    envelope = _require_object(parsed)
    require_exact_json_fields(
        envelope,
        allowed_fields=SIGNED_LICENSING_ENVELOPE_FIELDS,
        label="Entitlement",
    )
    if envelope.get("schema_version") != 1:
        raise ValidationError("Licensing entitlement envelope schema is invalid.")
    signature_domain = envelope.get("signature_domain")
    signature_text = envelope.get("signature")
    if not isinstance(signature_domain, str) or not signature_domain.isascii():
        raise ValidationError("Licensing entitlement signature domain is invalid.")
    if not isinstance(signature_text, str):
        raise ValidationError("Licensing entitlement signature is invalid.")
    payload = parse_entitlement_payload(envelope.get("payload"), signature_domain)
    _validate_binding(payload, binding)
    if payload.entitlement_type == "commercial_full_perpetual":
        validate_full_perpetual_grant_certificate(
            payload.values.get("grant_certificate"),
            trust_catalog,
            payload,
        )
    carried_snapshot = canonicalize_licensing_json(envelope.get("issuer_authorization"))
    if authorization_snapshot is not None and not hmac.compare_digest(
        authorization_snapshot, carried_snapshot
    ):
        raise ValidationError("Stored issuer authorization differs from the document.")
    authorization = trust_catalog.resolve_snapshot(
        carried_snapshot,
        issuer_key_id=envelope.get("issuer_key_id"),
        signature_domain=signature_domain,
        entitlement_type=payload.entitlement_type,
        licensed_product_scope=payload.licensed_product_scope,
        issued_at=payload.issued_at,
        allowed_personal_deployments=_personal_allowance(payload),
    )
    signature = decode_licensing_base64url(signature_text, expected_bytes=64)
    payload_bytes = canonicalize_licensing_json(payload.values)
    try:
        Ed25519PublicKey.from_public_bytes(authorization.public_key).verify(
            signature,
            b"".join((signature_domain.encode("ascii"), b"\0", payload_bytes)),
        )
    except InvalidSignature as exception:
        raise LicensingIntegrityError.for_failure(
            "invalid_signature",
            "Licensing entitlement signature is invalid.",
        ) from exception
    if (
        binding.current_generation is not None
        and binding.current_deployment_id == payload.deployment_id
        and payload.generation <= binding.current_generation
    ):
        if binding.current_document is None or not hmac.compare_digest(
            raw_document, binding.current_document
        ):
            raise ValidationError("Licensing entitlement generation does not advance.")
    return ValidatedEntitlement(
        canonical_document=raw_document,
        document_digest=f"sha256:{hashlib.sha256(raw_document).hexdigest()}",
        authorization_snapshot=authorization.authorization_bytes,
        entitlement_type=payload.entitlement_type,
        licensed_product_scope=payload.licensed_product_scope,
        instance_id=payload.instance_id,
        deployment_id=payload.deployment_id,
        generation=payload.generation,
        summary=build_safe_entitlement_summary(payload),
    )


def _validate_binding(payload: ParsedEntitlementPayload, binding: EntitlementBinding) -> None:
    edition_scope = "soai_core" if binding.edition == "soai-core" else "soai_os"
    scope_matches = payload.licensed_product_scope in {
        edition_scope,
        "soai_core_and_os",
    }
    if (
        not scope_matches
        or payload.instance_id != binding.instance_id
        or not hmac.compare_digest(payload.deployment_public_key, binding.deployment_public_key)
    ):
        raise LicensingIntegrityError.for_failure(
            "invalid_binding",
            "Licensing entitlement binding is invalid.",
        )


def build_safe_entitlement_summary(payload: ParsedEntitlementPayload) -> JSONDict:
    values = payload.values
    return {
        "entitlement_type": payload.entitlement_type,
        "licensed_product_scope": payload.licensed_product_scope,
        "deployment_product": payload.deployment_product,
        "licensed_capabilities": list(payload.capabilities),
        "deployment_id": payload.deployment_id,
        "effective_at": values["effective_at"],
        "term_starts_at": values.get("term_starts_at"),
        "term_ends_at": values.get("term_ends_at"),
        "continuity_starts_at": values.get("continuity_starts_at"),
        "continuity_ends_at": values.get("continuity_ends_at"),
        "deployment_environment": values.get("deployment_environment"),
    }


def _require_object(value: JSONValue) -> JSONDict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValidationError("Licensing entitlement must be an object.")
    return value


def _personal_allowance(payload: ParsedEntitlementPayload) -> int | None:
    value = payload.values.get("allowed_personal_deployments")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = (
    "EntitlementBinding",
    "ValidatedEntitlement",
    "build_safe_entitlement_summary",
    "validate_entitlement",
)
