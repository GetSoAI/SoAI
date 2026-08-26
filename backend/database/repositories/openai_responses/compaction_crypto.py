"""SoAI - OpenAI response compaction content encryption helpers [backend/database/repositories/openai_responses/compaction_crypto.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from database.repositories.openai_responses.crypto_ops import (
    decrypt_with_chain,
    resolve_encrypt_fernet,
)

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.types.json import JSONDict

__all__ = (
    "decrypt_compaction_content",
    "encrypt_compaction_content",
)


def encrypt_compaction_content(*, fernet_chain: tuple[Fernet, ...], content: JSONDict) -> str:
    if not isinstance(content, dict):
        raise ValidationError("content must be a JSON object.")
    payload_text = serialize_json_compact_stable(content)
    token_bytes = resolve_encrypt_fernet(fernet_chain).encrypt(payload_text.encode("utf-8"))
    return token_bytes.decode("utf-8")


def decrypt_compaction_content(
    *,
    fernet_chain: tuple[Fernet, ...],
    encrypted_content: str,
) -> JSONDict:
    token = encrypted_content.strip() if isinstance(encrypted_content, str) else ""
    if not token:
        raise ValidationError("encrypted_content must be a non-empty string.")
    decrypted = decrypt_with_chain(fernet_chain, token.encode("utf-8"))
    try:
        decoded = parse_json_value(decrypted.decode("utf-8"))
    except (UnicodeDecodeError, ValidationError) as exception:
        raise ValidationError(
            "Invalid encrypted content payload.",
            cause=exception,
        ) from exception
    if not isinstance(decoded, dict):
        raise ValidationError("Invalid encrypted content payload.")
    return dict(decoded)
