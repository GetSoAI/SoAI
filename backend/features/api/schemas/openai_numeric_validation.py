"""SoAI - OpenAI numeric schema validation helpers [backend/features/api/schemas/openai_numeric_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = ("reject_boolean_numeric_value",)


def reject_boolean_numeric_value(value: JSONValue, *, message: str) -> JSONValue:
    if isinstance(value, bool):
        raise ValidationError(message)
    return value
