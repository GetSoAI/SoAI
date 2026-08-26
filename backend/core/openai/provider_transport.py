"""SoAI - OpenAI-compatible provider transport helpers [backend/core/openai/provider_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlencode

from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int
from core.validation.string_mappings import validate_string_mapping

__all__ = (
    "build_openai_provider_headers",
    "build_openai_upstream_error_details",
    "compose_openai_provider_url",
    "normalize_openai_provider_query_params",
)

SOAI_REFERER = "https://soai.to/"
SOAI_TITLE = "SoAI"


def compose_openai_provider_url(
    api_url: str,
    endpoint: str,
    query_params: Mapping[str, str] | None = None,
) -> str:
    base = api_url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base}{path}"
    if query_params:
        encoded = urlencode(list(query_params.items()))
        if encoded:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}{encoded}"
    return url


def normalize_openai_provider_query_params(
    value: Mapping[str, JSONValue] | None,
) -> dict[str, str]:
    return validate_string_mapping(value) or {}


def build_openai_provider_headers(
    *,
    api_key: str | None,
    extra_headers: Mapping[str, JSONValue] | None,
    include_content_type: bool,
    referer: str = SOAI_REFERER,
    title: str = SOAI_TITLE,
) -> dict[str, str]:
    normalized_referer = referer.strip() or SOAI_REFERER
    normalized_title = title.strip() or SOAI_TITLE
    headers: dict[str, str] = {
        "Referer": normalized_referer,
        "HTTP-Referer": normalized_referer,
        "X-Title": normalized_title,
    }
    if include_content_type:
        headers["Content-Type"] = "application/json"
    normalized_key = api_key.strip() if isinstance(api_key, str) else ""
    if normalized_key:
        headers["Authorization"] = f"Bearer {normalized_key}"
    normalized_extra_headers = validate_string_mapping(extra_headers)
    if normalized_extra_headers:
        headers.update(normalized_extra_headers)
    return headers


def build_openai_upstream_error_details(
    provider_name: str | None,
    *,
    status: int | None = None,
    transport_error: bool = False,
    retry_after: str | None = None,
) -> JSONDict:
    normalized_provider_name = (
        provider_name.strip() if isinstance(provider_name, str) else ""
    ) or "Unknown Provider"
    details: JSONDict = {"upstream_provider": normalized_provider_name}
    if is_strict_int(status) and status > 0:
        details["upstream_http_status"] = status
    if transport_error:
        details["upstream_transport_error"] = True
    normalized_retry_after = retry_after.strip() if isinstance(retry_after, str) else ""
    if normalized_retry_after:
        details["upstream_retry_after"] = normalized_retry_after
    return details
