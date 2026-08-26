"""SoAI - Sanitized Messaging provider error code extraction [backend/features/messaging/provider_error_codes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.serialization.json_parsing import parse_json_value_or_none
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("read_messaging_provider_error_code",)

PROVIDER_ERROR_BODY_MAX_BYTES = 16_384
PROVIDER_ERROR_CODE_ABSOLUTE_MAXIMUM = 2_147_483_647


def _strict_int(value: JSONValue) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if abs(value) > PROVIDER_ERROR_CODE_ABSOLUTE_MAXIMUM:
        return None
    return value


def _read_bounded_body(response: httpx2.Response) -> bytes | None:
    try:
        body = response.content
    except (httpx2.ResponseNotRead, httpx2.StreamClosed):
        return None
    if not body or len(body) > PROVIDER_ERROR_BODY_MAX_BYTES:
        return None
    return body


def read_messaging_provider_error_code(response: httpx2.Response) -> int | None:
    body = _read_bounded_body(response)
    if body is None:
        return None
    payload = coerce_json_dict(parse_json_value_or_none(body, field="provider error"))
    if payload is None:
        return None
    telegram_code = _strict_int(payload.get("error_code"))
    if telegram_code is not None:
        return telegram_code
    graph_error = coerce_json_dict(payload.get("error"))
    if graph_error is None:
        return None
    return _strict_int(graph_error.get("code"))
