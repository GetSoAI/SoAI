"""SoAI - Stored licensing machine-request validation [backend/core/licensing/machine_request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.errors.exceptions import StateError, ValidationError
from core.licensing.canonicalization import (
    canonicalize_licensing_json,
    parse_canonical_licensing_document,
)
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.identifiers import (
    require_canonical_uuid4,
    require_licensing_identifier,
)
from core.types.json import JSONDict
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_int

_DEACTIVATION_FIELDS = frozenset(
    (
        "schema_version",
        "idempotency_key",
        "instance_id",
        "deployment_public_key",
        "request_nonce",
        "soai_version",
        "activation_id",
        "deployment_id",
        "reason",
        "signature",
    )
)


@dataclass(frozen=True, slots=True)
class ValidatedMachineRequest:
    payload: JSONDict
    signing_public_key: bytes


@dataclass(frozen=True, slots=True)
class ValidatedDeactivationRequest:
    idempotency_key: str
    instance_id: str
    deployment_public_key: bytes
    activation_id: str
    deployment_id: str
    reason: str


def validate_persisted_machine_request(
    content: bytes,
    expected_digest: str,
    signature_domain: str,
) -> ValidatedMachineRequest:
    try:
        parsed = parse_canonical_licensing_document(content)
    except ValidationError as exception:
        raise StateError("Stored licensing operation request is invalid.") from exception
    if not isinstance(parsed, dict):
        raise StateError("Stored licensing operation request is invalid.")
    signature_text = parsed.get("signature")
    public_key_text = parsed.get("deployment_public_key")
    if not isinstance(signature_text, str) or not isinstance(public_key_text, str):
        raise StateError("Stored licensing operation signature binding is invalid.")
    unsigned = dict(parsed)
    del unsigned["signature"]
    canonical_unsigned = canonicalize_licensing_json(unsigned)
    actual_digest = f"sha256:{hashlib.sha256(canonical_unsigned).hexdigest()}"
    if not hmac.compare_digest(expected_digest, actual_digest):
        raise StateError("Stored licensing operation digest is invalid.")
    try:
        public_key = decode_licensing_base64url(public_key_text, expected_bytes=32)
        signature = decode_licensing_base64url(signature_text, expected_bytes=64)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            b"".join((signature_domain.encode("ascii"), b"\0", canonical_unsigned)),
        )
    except (InvalidSignature, ValidationError, ValueError) as exception:
        raise StateError("Stored licensing operation signature is invalid.") from exception
    return ValidatedMachineRequest(dict(parsed), public_key)


def validate_deactivation_request(
    request: ValidatedMachineRequest,
) -> ValidatedDeactivationRequest:
    payload = request.payload
    try:
        require_exact_json_fields(
            payload,
            allowed_fields=_DEACTIVATION_FIELDS,
            label="Deactivation request",
        )
        instance_id = require_canonical_uuid4(payload.get("instance_id"))
        idempotency_key = require_licensing_identifier(
            payload.get("idempotency_key"),
            label="Licensing idempotency key",
        )
        activation_id = require_licensing_identifier(
            payload.get("activation_id"),
            label="Licensing activation identity",
        )
        deployment_id = require_licensing_identifier(
            payload.get("deployment_id"),
            label="Licensing deployment identity",
        )
        reason = payload.get("reason")
        if reason not in {"rehost", "retired", "disaster_recovery", "other"}:
            raise ValidationError("Deactivation request reason is invalid.")
        schema_version = require_int(
            payload.get("schema_version"),
            label="Deactivation request schema version",
            build_error=ValidationError,
        )
        if schema_version != 1:
            raise ValidationError("Deactivation request schema version is invalid.")
        version = payload.get("soai_version")
        if (
            not isinstance(version, str)
            or re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}", version) is None
        ):
            raise ValidationError("Deactivation request version is invalid.")
        nonce = payload.get("request_nonce")
        if not isinstance(nonce, str):
            raise ValidationError("Deactivation request nonce is invalid.")
        decode_licensing_base64url(nonce, expected_bytes=32)
    except ValidationError as exception:
        raise StateError("Stored deactivation request contract is invalid.") from exception
    return ValidatedDeactivationRequest(
        idempotency_key=idempotency_key,
        instance_id=instance_id,
        deployment_public_key=request.signing_public_key,
        activation_id=activation_id,
        deployment_id=deployment_id,
        reason=str(reason),
    )


__all__ = (
    "ValidatedDeactivationRequest",
    "ValidatedMachineRequest",
    "validate_deactivation_request",
    "validate_persisted_machine_request",
)
