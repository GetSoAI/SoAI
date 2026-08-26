"""SoAI - JSON payload to multipart field mapping [backend/features/api/routes/multipart_field_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from math import isfinite, isnan
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_multipart_style_fields_from_payload",)


def build_multipart_style_fields_from_payload(
    *,
    payload: JSONDict,
    allowed_fields: frozenset[str],
) -> dict[str, tuple[str, ...]]:
    fields: dict[str, tuple[str, ...]] = {}
    for raw_key, raw_value in payload.items():
        if raw_key not in allowed_fields:
            continue
        key = str(raw_key).strip()
        if not key or raw_value is None:
            continue
        if isinstance(raw_value, str):
            normalized = raw_value.strip()
            if normalized:
                fields[key] = (normalized,)
            continue
        if isinstance(raw_value, bool):
            fields[key] = ("true" if raw_value else "false",)
            continue
        if is_strict_int(raw_value):
            fields[key] = (str(raw_value),)
            continue
        if isinstance(raw_value, float):
            if isnan(raw_value):
                raise ValidationError(f"Field '{key}' must not be NaN.")
            if not isfinite(raw_value):
                raise ValidationError(f"Field '{key}' must be finite.")
            fields[key] = (str(raw_value),)
            continue
        if isinstance(raw_value, list):
            items: list[str] = []
            for item in raw_value:
                if not isinstance(item, str):
                    raise ValidationError(f"Field '{key}' list must contain strings only.")
                normalized_item = item.strip()
                if normalized_item:
                    items.append(normalized_item)
            if items:
                fields[key] = tuple(items)
            continue
        if isinstance(raw_value, dict):
            fields[key] = (serialize_json_compact_stable_strict(raw_value),)
            continue
        raw_type = type(raw_value).__name__
        raise ValidationError(f"Field '{key}' has an unsupported type: {raw_type}.")
    return fields
