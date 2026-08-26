"""SoAI - Signed licensing status validation [backend/core/licensing/licensing_status_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import (
    canonicalize_licensing_json,
    parse_canonical_licensing_document,
)
from core.licensing.constants import SIGNED_LICENSING_ENVELOPE_FIELDS
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.errors import LicensingIntegrityError
from core.licensing.identifiers import require_canonical_uuid4, require_licensing_identifier
from core.licensing.timestamps import parse_licensing_timestamp
from core.licensing.trust import IssuerAuthorizationCatalog
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields

LICENSING_STATUS_SIGNATURE_DOMAIN = "soai-licensing-status-v1"
LICENSING_STATUS_REASON_CATEGORIES = frozenset(
    (
        "customer_request",
        "fraud",
        "legal_requirement",
        "material_breach",
        "payment_default",
    )
)
_PAYLOAD_FIELDS = frozenset(
    (
        "schema_version",
        "document_type",
        "license_id",
        "instance_id",
        "deployment_id",
        "state",
        "reason_category",
        "effective_at",
        "issued_at",
        "entitlement_generation",
    )
)


@dataclass(frozen=True, slots=True)
class LicensingStatusBinding:
    instance_id: str
    deployment_id: str
    license_id: str
    entitlement_type: str
    licensed_product_scope: str
    current_generation: int
    current_document: bytes | None

    def __post_init__(self) -> None:
        require_canonical_uuid4(self.instance_id)
        require_licensing_identifier(
            self.deployment_id,
            label="Licensing deployment_id",
        )
        require_licensing_identifier(
            self.license_id,
            label="Licensing license_id",
        )
        if self.entitlement_type not in {
            "commercial_term",
            "commercial_continuity",
            "personal_os_perpetual",
            "commercial_full_perpetual",
        }:
            raise ValidationError("Licensing status entitlement binding is invalid.")
        if self.licensed_product_scope not in {
            "soai_core",
            "soai_os",
            "soai_core_and_os",
        }:
            raise ValidationError("Licensing status product binding is invalid.")
        if self.current_generation < 1:
            raise ValidationError("Licensing status generation binding is invalid.")


@dataclass(frozen=True, slots=True)
class ValidatedLicensingStatus:
    canonical_document: bytes
    document_digest: str
    authorization_snapshot: bytes
    state: str
    generation: int
    effective_at: datetime
    issued_at: datetime


def validate_signed_licensing_status(
    raw_document: bytes,
    trust_catalog: IssuerAuthorizationCatalog,
    binding: LicensingStatusBinding,
    authorization_snapshot: bytes | None = None,
) -> ValidatedLicensingStatus:
    envelope = _require_object(parse_canonical_licensing_document(raw_document), "envelope")
    require_exact_json_fields(
        envelope,
        allowed_fields=SIGNED_LICENSING_ENVELOPE_FIELDS,
        label="Licensing status",
    )
    if envelope.get("schema_version") != 1:
        raise ValidationError("Licensing status envelope schema is invalid.")
    if envelope.get("signature_domain") != LICENSING_STATUS_SIGNATURE_DOMAIN:
        raise ValidationError("Licensing status signature domain is invalid.")
    signature_text = envelope.get("signature")
    if not isinstance(signature_text, str):
        raise ValidationError("Licensing status signature is invalid.")
    payload = _require_object(envelope.get("payload"), "payload")
    require_exact_json_fields(
        payload, allowed_fields=_PAYLOAD_FIELDS, label="Licensing status payload"
    )
    state, _reason, generation, effective_at, issued_at = _validate_payload(payload, binding)
    carried_snapshot = canonicalize_licensing_json(envelope.get("issuer_authorization"))
    if authorization_snapshot is not None and not hmac.compare_digest(
        authorization_snapshot, carried_snapshot
    ):
        raise ValidationError("Stored issuer authorization differs from the status document.")
    authorization = trust_catalog.resolve_snapshot(
        carried_snapshot,
        issuer_key_id=envelope.get("issuer_key_id"),
        signature_domain=LICENSING_STATUS_SIGNATURE_DOMAIN,
        entitlement_type="licensing_status",
        licensed_product_scope=binding.licensed_product_scope,
        issued_at=issued_at,
        allowed_personal_deployments=None,
    )
    signature = decode_licensing_base64url(signature_text, expected_bytes=64)
    try:
        Ed25519PublicKey.from_public_bytes(authorization.public_key).verify(
            signature,
            b"".join(
                (
                    LICENSING_STATUS_SIGNATURE_DOMAIN.encode("ascii"),
                    b"\0",
                    canonicalize_licensing_json(payload),
                )
            ),
        )
    except InvalidSignature as exception:
        raise LicensingIntegrityError.for_failure(
            "invalid_signature", "Licensing status signature is invalid."
        ) from exception
    if generation <= binding.current_generation and (
        binding.current_document is None
        or not hmac.compare_digest(raw_document, binding.current_document)
    ):
        raise ValidationError("Licensing status generation does not advance.")
    return ValidatedLicensingStatus(
        raw_document,
        f"sha256:{hashlib.sha256(raw_document).hexdigest()}",
        authorization.authorization_bytes,
        state,
        generation,
        effective_at,
        issued_at,
    )


def _validate_payload(
    payload: JSONDict,
    binding: LicensingStatusBinding,
) -> tuple[str, str, int, datetime, datetime]:
    if payload.get("schema_version") != 1 or payload.get("document_type") != "licensing_status":
        raise ValidationError("Licensing status payload contract is invalid.")
    state = payload.get("state")
    reason = payload.get("reason_category")
    generation = payload.get("entitlement_generation")
    effective_at = parse_licensing_timestamp(payload.get("effective_at"), field="effective_at")
    issued_at = parse_licensing_timestamp(payload.get("issued_at"), field="issued_at")
    if state not in {"suspended", "terminated"}:
        raise ValidationError("Licensing status payload values are invalid.")
    if not isinstance(reason, str) or reason not in LICENSING_STATUS_REASON_CATEGORIES:
        raise ValidationError("Licensing status payload values are invalid.")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise ValidationError("Licensing status payload values are invalid.")
    if effective_at > issued_at:
        raise ValidationError("Licensing status payload values are invalid.")
    if (
        payload.get("instance_id") != binding.instance_id
        or payload.get("deployment_id") != binding.deployment_id
        or payload.get("license_id") != binding.license_id
    ):
        raise LicensingIntegrityError.for_failure(
            "invalid_binding", "Licensing status binding is invalid."
        )
    resolved_state = "suspended" if state == "suspended" else "terminated"
    return resolved_state, reason, generation, effective_at, issued_at


def _require_object(value: JSONValue, label: str) -> JSONDict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValidationError(f"Licensing status {label} must be an object.")
    return value


__all__ = (
    "LICENSING_STATUS_REASON_CATEGORIES",
    "LICENSING_STATUS_SIGNATURE_DOMAIN",
    "LicensingStatusBinding",
    "ValidatedLicensingStatus",
    "validate_signed_licensing_status",
)
