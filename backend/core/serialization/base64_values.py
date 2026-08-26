"""SoAI - Shared base64 value encoding and decoding helpers [backend/core/serialization/base64_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import base64

from core.errors.exceptions import ValidationError

__all__ = (
    "decode_base64_ascii",
    "decode_base64_ascii_urlsafe",
    "encode_base64_ascii",
    "encode_base64_urlsafe_ascii",
    "extract_base64_data_payload",
)


def encode_base64_ascii(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def encode_base64_urlsafe_ascii(data: bytes, *, strip_padding: bool = False) -> str:
    encoded = base64.urlsafe_b64encode(data).decode("ascii")
    if strip_padding:
        return encoded.rstrip("=")
    return encoded


def decode_base64_ascii(value: str, *, error_message: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as exception:
        raise ValidationError(error_message) from exception


def decode_base64_ascii_urlsafe(value: str, *, error_message: str) -> bytes:
    try:
        return base64.b64decode(value, altchars=b"-_", validate=True)
    except ValueError as exception:
        raise ValidationError(error_message) from exception


def extract_base64_data_payload(value: str) -> str:
    raw = value.strip()
    if not raw.startswith("data:"):
        return raw
    comma_index = raw.find(",")
    if comma_index > 0 and "base64" in raw[:comma_index].lower():
        return raw[comma_index + 1 :]
    return raw
