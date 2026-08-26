"""SoAI - Messaging provider response identities [backend/core/messaging/provider_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("require_messaging_provider_response_id",)


def require_messaging_provider_response_id(value: JSONValue, label: str) -> str:
    if isinstance(value, bool):
        raise ValidationError(f"{label} is invalid.")
    if isinstance(value, int):
        return str(value)
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise ValidationError(f"{label} is invalid.")
    return normalized
