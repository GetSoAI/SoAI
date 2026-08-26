"""SoAI - HTTP response JSON decoding helpers [backend/core/network/http_json.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2

from core.errors.exceptions import ValidationError
from core.network.protocols import HTTPJsonResponseProtocol
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict, JSONValue, is_json_value

__all__ = (
    "read_http_json_dict",
    "read_http_json_value",
)


def read_http_json_value(response: HTTPJsonResponseProtocol, *, field: str) -> JSONValue:
    try:
        raw = response.json()
    except (
        ValueError,
        TypeError,
        httpx2.ResponseNotRead,
        httpx2.StreamClosed,
    ) as exception:
        raise ValidationError(f"{field} must be valid JSON.") from exception
    normalized = normalize_for_json(raw)
    if is_json_value(normalized):
        return normalized
    raise ValidationError(f"{field} must be JSON-compatible.")


def read_http_json_dict(response: HTTPJsonResponseProtocol, *, field: str) -> JSONDict:
    value = read_http_json_value(response, field=field)
    if isinstance(value, dict):
        return value
    raise ValidationError(f"{field} must be a JSON object.")
