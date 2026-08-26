"""SoAI - SoAIError HTTP response field extraction [backend/core/errors/soai_error_http_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.errors.exceptions import SoAIError
    from core.types.json import JSONDict

__all__ = ("extract_soai_error_http_fields",)


def extract_soai_error_http_fields(
    error: SoAIError,
) -> tuple[int, JSONDict | None, str | int | None, Mapping[str, str] | None]:
    try:
        http_status = int(error.http_status)
    except (AttributeError, TypeError, ValueError):
        http_status = 500
    try:
        details_value = error.details
    except AttributeError:
        details_value = None
    details = coerce_json_dict(details_value)
    try:
        code_value = error.code
    except AttributeError:
        code_value = None
    soai_code = code_value if isinstance(code_value, str | int) else None
    try:
        headers_value = error.headers
    except AttributeError:
        headers_value = None
    headers = headers_value if isinstance(headers_value, Mapping) else None
    return (http_status, details, soai_code, headers)
