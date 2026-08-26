"""SoAI - Backend variant ID validation [backend/core/plugins/backend_variant_ids.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "AUTO_BACKEND_VARIANT_ID",
    "normalize_backend_variant_id",
    "require_backend_variant_id",
)

AUTO_BACKEND_VARIANT_ID = "auto"
_VARIANT_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"


def normalize_backend_variant_id(value: JSONValue) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if re.fullmatch(_VARIANT_ID_PATTERN, lowered) is None:
        return None
    return lowered


def require_backend_variant_id(value: JSONValue) -> str:
    variant_id = normalize_backend_variant_id(value)
    if variant_id is None:
        raise ValidationError("backend_variant_id must be a valid backend variant ID.")
    return variant_id
