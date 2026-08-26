"""SoAI - API command response timeout coercion [backend/features/api/runtime/response_timeout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.numbers import coerce_float_from_json
from core.validation.record_fields import require_number
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from core.runtime.protocols import ConnectionProtocol
    from core.types.json import JSONValue

__all__ = (
    "coerce_finite_response_timeout",
    "require_response_timeout_value",
)


def coerce_finite_response_timeout(value: JSONValue) -> float | None:
    try:
        candidate = require_number(
            value,
            label="response_timeout",
            build_error=ValidationError,
        )
    except ValidationError:
        return None
    return float(candidate)


def require_response_timeout_value(
    request: ConnectionProtocol,
    value: JSONValue,
    *,
    message: str,
) -> float:
    parsed = coerce_float_from_json(value, default=None, allow_nonfinite=False)
    if parsed is None:
        raise_invalid_request(request, message)
    return parsed
