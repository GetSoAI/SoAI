"""SoAI - API JSON response body construction and parsing [backend/features/api/runtime/response_body.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.types.json import JSONValue

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "create_json_body_response",
    "parse_response_body_json_dict",
    "parse_response_body_json_value",
    "read_response_body_bytes",
)

_CACHE_CONTROL_HEADER = "Cache-Control"
_NO_STORE_CACHE_CONTROL = "no-store"


def create_json_body_response(
    *,
    content: JSONValue,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    no_store: bool = False,
) -> JSONResponse:
    response_headers = dict(headers) if headers is not None else {}
    if no_store and all(header_name.lower() != "cache-control" for header_name in response_headers):
        response_headers[_CACHE_CONTROL_HEADER] = _NO_STORE_CACHE_CONTROL
    normalized_headers = response_headers if response_headers else None
    return JSONResponse(status_code=status_code, content=content, headers=normalized_headers)


def read_response_body_bytes(response: Response) -> bytes | None:
    try:
        body_bytes = response.body
    except AttributeError:
        return None
    if not isinstance(body_bytes, bytes | bytearray) or not body_bytes:
        return None
    return bytes(body_bytes)


def parse_response_body_json_value(response: Response, *, field: str) -> JSONValue:
    body_bytes = read_response_body_bytes(response)
    if body_bytes is None:
        raise ValidationError(f"{field} body is unavailable.")
    return parse_json_value(body_bytes, field=field)


def parse_response_body_json_dict(response: Response, *, field: str) -> JSONDict:
    body_bytes = read_response_body_bytes(response)
    if body_bytes is None:
        raise ValidationError(f"{field} body is unavailable.")
    return parse_json_dict(body_bytes, field=field)
