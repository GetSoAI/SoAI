"""SoAI - String mapping validation helpers [backend/core/validation/string_mappings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Hashable

    from core.types.json import JSONValue

__all__ = ("validate_string_mapping",)


def validate_string_mapping(
    value: JSONValue | Mapping[Hashable, JSONValue],
) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValidationError("Mapping value must be a mapping.")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            raise ValidationError("Mapping keys cannot be empty.")
        normalized[key] = "" if raw_value is None else str(raw_value)
    return normalized
