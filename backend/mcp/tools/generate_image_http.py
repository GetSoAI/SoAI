"""SoAI - MCP generate image HTTP helpers [backend/mcp/tools/generate_image_http.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ValidationError
from core.security.response_redaction import (
    REDACTED_PLACEHOLDER,
    redact_response_payload,
)
from core.serialization.json_parsing import parse_json_dict
from mcp.tools.provider_http import (
    build_provider_http_status_message,
    parse_provider_json_dict,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_image_provider_http_error", "read_image_provider_json")


async def read_image_provider_json(response: httpx2.Response, *, field: str) -> JSONDict:
    raw_body = await response.aread()
    return parse_provider_json_dict(
        raw_body,
        field=field,
        invalid_message="Image generation provider returned invalid JSON.",
    )


async def build_image_provider_http_error(response: httpx2.Response) -> str:
    status_code = int(response.status_code)
    status_message = _build_status_message(status_code)
    raw_body = await response.aread()
    provider_detail = _extract_provider_error_detail(raw_body)
    if provider_detail is None:
        return status_message
    return f"{status_message} Provider detail: {provider_detail}"


def _build_status_message(status_code: int) -> str:
    return build_provider_http_status_message(
        status_code,
        provider_label="Image generation provider",
        auth_rejected_message="Image generation provider rejected the configured credentials.",
        payment_required_message=(
            "Image generation provider requires payment or credits for this request."
        ),
        not_found_message="Image generation provider endpoint was not found.",
        timeout_message="Image generation provider timed out while processing the request.",
        rate_limit_message="Image generation provider rate limit was reached. Retry later.",
        unavailable_message="Image generation provider is temporarily unavailable.",
    )


def _extract_provider_error_detail(raw_body: bytes) -> str | None:
    try:
        payload = parse_json_dict(raw_body, field="image provider error response")
    except ValidationError:
        return None
    sanitized = redact_response_payload(payload)
    if not isinstance(sanitized, dict):
        return None
    details: list[str] = []
    for key in ("error", "message", "detail"):
        value = sanitized.get(key)
        formatted = _format_provider_error_value(value)
        if formatted is not None:
            details.append(formatted)
    errors_value = sanitized.get("errors")
    if isinstance(errors_value, dict):
        for key, value in errors_value.items():
            formatted = _format_provider_error_value(value)
            if formatted is not None:
                details.append(f"{key}: {formatted}")
    if not details:
        return None
    return "; ".join(details)


def _format_provider_error_value(value: JSONValue) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized or normalized == REDACTED_PLACEHOLDER:
            return None
        return normalized[:300]
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return None
