"""SoAI - Licensing V1 base64url contracts [backend/core/licensing/encoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError

__all__ = ("decode_licensing_base64url",)
from core.serialization.base64_values import (
    decode_base64_ascii_urlsafe,
    encode_base64_urlsafe_ascii,
)


def decode_licensing_base64url(value: str, *, expected_bytes: int) -> bytes:
    if (
        not value
        or not value.isascii()
        or "=" in value
        or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
    ):
        raise ValidationError("Licensing base64url value is not canonical.")
    padding = "=" * (-len(value) % 4)
    decoded = decode_base64_ascii_urlsafe(
        value + padding,
        error_message="Licensing base64url value is invalid.",
    )
    if len(decoded) != expected_bytes:
        raise ValidationError("Licensing base64url value has an invalid length.")
    canonical = encode_base64_urlsafe_ascii(decoded, strip_padding=True)
    if canonical != value:
        raise ValidationError("Licensing base64url value is not canonical.")
    return decoded
