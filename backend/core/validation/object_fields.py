"""SoAI - Exact JSON object field validation [backend/core/validation/object_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

__all__ = ("require_exact_json_fields",)


def require_exact_json_fields(
    payload: JSONDict,
    *,
    allowed_fields: Collection[str],
    label: str,
) -> None:
    unexpected_fields = sorted(str(field) for field in payload if field not in allowed_fields)
    if unexpected_fields:
        raise ValidationError(f"{label} contains unexpected field '{unexpected_fields[0]}'.")
