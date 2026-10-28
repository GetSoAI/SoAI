"""SoAI - OpenAI numeric schema validation helpers [backend/features/api/schemas/openai_numeric_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.types.json import JSONValue

__all__ = ("reject_boolean_numeric_value",)


def reject_boolean_numeric_value(
    value: JSONValue, *, message: str, param: str | None = None
) -> JSONValue:
    if isinstance(value, bool):
        error = ValidationError(message)
        if param is not None:
            apply_public_error_payload(
                error,
                ErrorPublicPayload(
                    code=error.code, message=message, param=param, http_status=error.http_status
                ),
            )
        raise error
    return value
