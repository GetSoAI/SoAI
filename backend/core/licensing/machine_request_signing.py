"""SoAI - Canonical machine request signing [backend/core/licensing/machine_request_signing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import canonicalize_licensing_json
from core.licensing.identifiers import require_canonical_uuid4, require_licensing_identifier
from core.serialization.base64_values import encode_base64_urlsafe_ascii
from core.types.json import JSONDict

MAX_MACHINE_REQUEST_BYTES = 16 * 1024


@dataclass(frozen=True, slots=True)
class PreparedLicensingRequest:
    canonical_document: bytes = field(repr=False)
    request_digest: str
    request_nonce: bytes = field(repr=False)


def prepare_signed_machine_request(
    private_key: Ed25519PrivateKey,
    operation: str,
    idempotency_key: str,
    instance_id: str,
    soai_version: str,
    request_nonce: bytes | None,
    specific: JSONDict,
) -> PreparedLicensingRequest:
    require_licensing_identifier(idempotency_key, label="Licensing idempotency key")
    require_canonical_uuid4(instance_id)
    if re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}", soai_version) is None:
        raise ValidationError("SoAI version is invalid for licensing.")
    nonce = request_nonce if request_nonce is not None else secrets.token_bytes(32)
    if not isinstance(nonce, bytes) or len(nonce) != 32:
        raise ValidationError("Licensing request nonce must contain exactly 32 bytes.")
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    unsigned: JSONDict = {
        "schema_version": 1,
        "idempotency_key": idempotency_key,
        "instance_id": instance_id,
        "deployment_public_key": _encode(public_key),
        "request_nonce": _encode(nonce),
        "soai_version": soai_version,
        **specific,
    }
    canonical_unsigned = canonicalize_licensing_json(unsigned)
    domain = f"soai-licensing-{operation}-request-v1".encode("ascii")
    complete = dict(unsigned)
    complete["signature"] = _encode(private_key.sign(domain + b"\0" + canonical_unsigned))
    canonical_document = canonicalize_licensing_json(complete)
    if len(canonical_document) > MAX_MACHINE_REQUEST_BYTES:
        raise ValidationError("Licensing machine request exceeds its V1 size limit.")
    return PreparedLicensingRequest(
        canonical_document,
        f"sha256:{hashlib.sha256(canonical_unsigned).hexdigest()}",
        nonce,
    )


def _encode(value: bytes) -> str:
    return encode_base64_urlsafe_ascii(value, strip_padding=True)


__all__ = (
    "MAX_MACHINE_REQUEST_BYTES",
    "PreparedLicensingRequest",
    "prepare_signed_machine_request",
)
