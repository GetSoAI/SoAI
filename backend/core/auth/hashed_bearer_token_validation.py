"""SoAI - Salted bearer token record validation [backend/core/auth/hashed_bearer_token_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from dataclasses import dataclass

from core.auth.api_keys import hash_api_key
from core.types.json import JSONDict

__all__ = (
    "HashedBearerTokenValidationResult",
    "validate_hashed_bearer_token_record",
)


@dataclass(frozen=True, slots=True)
class HashedBearerTokenValidationResult:
    valid: bool
    reason: str
    token_id: str | None


def validate_hashed_bearer_token_record(
    *,
    record: JSONDict,
    provided_token: str,
    id_field: str,
    salt_field: str,
    hash_field: str,
    secret_keys: tuple[str, ...],
) -> HashedBearerTokenValidationResult:
    token_id_value = record.get(id_field)
    token_id = token_id_value if isinstance(token_id_value, str) and token_id_value else None
    salt_value = record.get(salt_field)
    hashed_value = record.get(hash_field)
    if not (isinstance(salt_value, str) and isinstance(hashed_value, str)):
        return HashedBearerTokenValidationResult(
            valid=False,
            reason="invalid_record",
            token_id=None,
        )
    signature_matches = False
    for secret_key in secret_keys:
        computed_hash = hash_api_key(
            provided_token,
            salt_value,
            secret_key=secret_key,
        )
        signature_matches = secrets.compare_digest(computed_hash, hashed_value) or signature_matches
    if not signature_matches:
        return HashedBearerTokenValidationResult(
            valid=False,
            reason="signature_mismatch",
            token_id=token_id,
        )
    if not token_id:
        return HashedBearerTokenValidationResult(
            valid=False,
            reason="invalid_record",
            token_id=None,
        )
    return HashedBearerTokenValidationResult(valid=True, reason="ok", token_id=token_id)
