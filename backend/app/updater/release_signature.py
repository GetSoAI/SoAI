"""SoAI - Ed25519 release manifest verification [backend/app/updater/release_signature.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary

__all__ = ("release_public_key_fingerprint", "verify_release_manifest_signature")

ED25519_PUBLIC_KEY_BYTES = 32
ED25519_SIGNATURE_BYTES = 64


def _decode_base64_exact(raw_bytes: bytes, *, expected_size: int, label: str) -> bytes:
    try:
        decoded = base64.b64decode(raw_bytes.strip(), validate=True)
    except ValueError as exception:
        raise ValidationError(f"{label} is not valid Base64.") from exception
    if len(decoded) != expected_size:
        raise ValidationError(f"{label} has an invalid length.")
    return decoded


def _read_release_public_key(public_key_path: str) -> bytes:
    try:
        with open_binary(public_key_path, mode="rb") as file_handle:
            return _decode_base64_exact(
                file_handle.read(),
                expected_size=ED25519_PUBLIC_KEY_BYTES,
                label="Release public key",
            )
    except OSError as exception:
        raise ValidationError("Release public key is missing or unreadable.") from exception


def release_public_key_fingerprint(public_key_path: str) -> str:
    return hashlib.sha256(_read_release_public_key(public_key_path)).hexdigest()


def verify_release_manifest_signature(
    *,
    manifest_bytes: bytes,
    signature_bytes: bytes,
    public_key_path: str,
) -> None:
    try:
        public_key_bytes = _read_release_public_key(public_key_path)
        signature = _decode_base64_exact(
            signature_bytes,
            expected_size=ED25519_SIGNATURE_BYTES,
            label="Release manifest signature",
        )
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, manifest_bytes)
    except InvalidSignature as exception:
        raise ValidationError("Release manifest signature verification failed.") from exception
