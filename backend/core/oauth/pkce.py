"""SoAI - OAuth PKCE helpers [backend/core/oauth/pkce.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import secrets

from core.errors.exceptions import ValidationError
from core.serialization.base64_values import encode_base64_urlsafe_ascii

__all__ = (
    "code_challenge_s256",
    "generate_code_verifier",
)

_MIN_VERIFIER_LEN = 43
_MAX_VERIFIER_LEN = 128


def generate_code_verifier(*, length: int = 96) -> str:
    if length < _MIN_VERIFIER_LEN or length > _MAX_VERIFIER_LEN:
        raise ValidationError("PKCE code_verifier length must be between 43 and 128.")
    while True:
        verifier = secrets.token_urlsafe(length)
        if len(verifier) >= _MIN_VERIFIER_LEN:
            return verifier[:length]


def code_challenge_s256(code_verifier: str) -> str:
    if not code_verifier:
        raise ValidationError("PKCE code_verifier is required.")
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return encode_base64_urlsafe_ascii(digest, strip_padding=True)
