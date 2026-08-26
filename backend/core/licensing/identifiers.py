"""SoAI - Licensing V1 identifier validation [backend/core/licensing/identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from uuid import UUID

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = ("require_canonical_uuid4", "require_licensing_identifier")


def require_canonical_uuid4(value: JSONValue) -> str:
    if not isinstance(value, str):
        raise ValidationError("Instance identity must be a canonical UUIDv4.")
    try:
        parsed = UUID(value)
    except ValueError as exception:
        raise ValidationError("Instance identity must be a canonical UUIDv4.") from exception
    if parsed.version != 4 or str(parsed) != value:
        raise ValidationError("Instance identity must be a canonical UUIDv4.")
    return value


def require_licensing_identifier(value: JSONValue, *, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value) is None:
        raise ValidationError(f"{label} is invalid.")
    return value
