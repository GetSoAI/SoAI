"""SoAI - Signed deployment rehost transitions [backend/core/licensing/deployment_transition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hmac
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import (
    canonicalize_licensing_json,
    parse_canonical_licensing_document,
)
from core.licensing.encoding import decode_licensing_base64url
from core.licensing.identifiers import (
    require_canonical_uuid4,
    require_licensing_identifier,
)
from core.serialization.base64_values import encode_base64_urlsafe_ascii
from core.types.json import JSONDict, JSONValue
from core.validation.epoch import require_unix_epoch_ms
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_int

DEPLOYMENT_REHOST_SIGNATURE_DOMAIN = "soai-licensing-deployment-rehost-v1"
_TRANSITION_FIELDS = frozenset(
    (
        "schema_version",
        "transition_type",
        "operation_id",
        "instance_id",
        "deployment_id",
        "old_deployment_public_key",
        "new_deployment_public_key",
        "completed_at_ms",
        "signature",
    )
)


@dataclass(frozen=True, slots=True)
class DeploymentRehostTransition:
    operation_id: str
    instance_id: str
    deployment_id: str
    old_public_key: bytes
    new_public_key: bytes
    completed_at_ms: int
    canonical_document: bytes


def prepare_deployment_rehost_transition(
    old_private_key: Ed25519PrivateKey,
    *,
    operation_id: str,
    instance_id: str,
    deployment_id: str,
    new_public_key: bytes,
    completed_at_ms: int,
) -> DeploymentRehostTransition:
    old_public_key = old_private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    _validate_transition_values(
        operation_id,
        instance_id,
        deployment_id,
        old_public_key,
        new_public_key,
        completed_at_ms,
    )
    unsigned: JSONDict = {
        "schema_version": 1,
        "transition_type": "rehost",
        "operation_id": operation_id,
        "instance_id": instance_id,
        "deployment_id": deployment_id,
        "old_deployment_public_key": _encode(old_public_key),
        "new_deployment_public_key": _encode(new_public_key),
        "completed_at_ms": completed_at_ms,
    }
    canonical_unsigned = canonicalize_licensing_json(unsigned)
    complete = dict(unsigned)
    complete["signature"] = _encode(
        old_private_key.sign(
            b"".join(
                (
                    DEPLOYMENT_REHOST_SIGNATURE_DOMAIN.encode("ascii"),
                    b"\0",
                    canonical_unsigned,
                )
            )
        )
    )
    canonical_document = canonicalize_licensing_json(complete)
    return DeploymentRehostTransition(
        operation_id,
        instance_id,
        deployment_id,
        old_public_key,
        new_public_key,
        completed_at_ms,
        canonical_document,
    )


def validate_deployment_rehost_transition(content: bytes) -> DeploymentRehostTransition:
    parsed = parse_canonical_licensing_document(content)
    if not isinstance(parsed, dict):
        raise ValidationError("Deployment rehost transition must be an object.")
    require_exact_json_fields(
        parsed,
        allowed_fields=_TRANSITION_FIELDS,
        label="Deployment rehost transition",
    )
    schema_version = require_int(
        parsed.get("schema_version"),
        label="Deployment rehost schema version",
        build_error=ValidationError,
    )
    if schema_version != 1 or parsed.get("transition_type") != "rehost":
        raise ValidationError("Deployment rehost transition type is invalid.")
    operation_id = require_canonical_uuid4(parsed.get("operation_id"))
    instance_id = require_canonical_uuid4(parsed.get("instance_id"))
    deployment_id = require_licensing_identifier(
        parsed.get("deployment_id"),
        label="Licensing deployment identity",
    )
    old_public_key = _decode_key(parsed.get("old_deployment_public_key"))
    new_public_key = _decode_key(parsed.get("new_deployment_public_key"))
    completed_at_ms = require_unix_epoch_ms(
        parsed.get("completed_at_ms"),
        error_message="Deployment rehost completion time is invalid.",
    )
    _validate_transition_values(
        operation_id,
        instance_id,
        deployment_id,
        old_public_key,
        new_public_key,
        completed_at_ms,
    )
    signature_text = parsed.get("signature")
    if not isinstance(signature_text, str):
        raise ValidationError("Deployment rehost signature is invalid.")
    unsigned = dict(parsed)
    del unsigned["signature"]
    try:
        Ed25519PublicKey.from_public_bytes(old_public_key).verify(
            decode_licensing_base64url(signature_text, expected_bytes=64),
            b"".join(
                (
                    DEPLOYMENT_REHOST_SIGNATURE_DOMAIN.encode("ascii"),
                    b"\0",
                    canonicalize_licensing_json(unsigned),
                )
            ),
        )
    except (InvalidSignature, ValueError) as exception:
        raise ValidationError("Deployment rehost signature is invalid.") from exception
    return DeploymentRehostTransition(
        operation_id,
        instance_id,
        deployment_id,
        old_public_key,
        new_public_key,
        completed_at_ms,
        content,
    )


def _validate_transition_values(
    operation_id: str,
    instance_id: str,
    deployment_id: str,
    old_public_key: bytes,
    new_public_key: bytes,
    completed_at_ms: int,
) -> None:
    require_canonical_uuid4(operation_id)
    require_canonical_uuid4(instance_id)
    require_licensing_identifier(deployment_id, label="Licensing deployment identity")
    require_unix_epoch_ms(
        completed_at_ms,
        error_message="Deployment rehost completion time is invalid.",
    )
    if len(old_public_key) != 32 or len(new_public_key) != 32:
        raise ValidationError("Deployment rehost key length is invalid.")
    if hmac.compare_digest(old_public_key, new_public_key):
        raise ValidationError("Deployment rehost keys must differ.")


def _decode_key(value: JSONValue) -> bytes:
    if not isinstance(value, str):
        raise ValidationError("Deployment rehost key is invalid.")
    return decode_licensing_base64url(value, expected_bytes=32)


def _encode(value: bytes) -> str:
    return encode_base64_urlsafe_ascii(value, strip_padding=True)


__all__ = (
    "DEPLOYMENT_REHOST_SIGNATURE_DOMAIN",
    "DeploymentRehostTransition",
    "prepare_deployment_rehost_transition",
    "validate_deployment_rehost_transition",
)
