"""SoAI - OpenAI Responses encryption helpers [backend/database/repositories/openai_responses/crypto_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from core.errors.exceptions import ValidationError

__all__ = (
    "decrypt_with_chain",
    "resolve_encrypt_fernet",
)


def resolve_encrypt_fernet(fernet_chain: tuple[Fernet, ...]) -> Fernet:
    if not isinstance(fernet_chain, tuple) or not fernet_chain:
        raise ValidationError("OpenAI responses encryption keychain is not configured.")
    first = fernet_chain[0]
    if not isinstance(first, Fernet):
        raise ValidationError("OpenAI responses encryption keychain contains invalid entries.")
    return first


def decrypt_with_chain(fernet_chain: tuple[Fernet, ...], token: bytes) -> bytes:
    if not isinstance(fernet_chain, tuple) or not fernet_chain:
        raise ValidationError("OpenAI responses encryption keychain is not configured.")
    last_error: Exception | None = None
    for instance in fernet_chain:
        if not isinstance(instance, Fernet):
            continue
        try:
            return instance.decrypt(token)
        except InvalidToken as exception:
            last_error = exception
            continue
    raise ValidationError(
        "Invalid encrypted content.",
        details={"cause": str(last_error) if last_error is not None else "invalid_token"},
    )
