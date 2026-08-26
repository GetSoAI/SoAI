"""SoAI - HTTP request session payload parsing and persistence [backend/mcp/tools/http_request_sessions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from mcp.tools.argument_fields import (
    require_json_object,
    require_string_map,
)
from mcp.tools.error import MCPToolError
from mcp.tools.http_request_cookie_jar import (
    parse_session_cookies,
    serialize_session_cookies,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "apply_redirect_session_headers",
    "apply_session_headers",
    "build_updated_session_payload",
    "parse_http_session_payload",
)

_SESSION_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"cookies", "default_headers", "per_host_headers"},
)


def parse_http_session_payload(
    raw: JSONValue,
    *,
    field_name: str,
    request_url: str,
) -> tuple[httpx2.Cookies, dict[str, str], dict[str, dict[str, str]], JSONDict]:
    if raw is None:
        return (
            httpx2.Cookies(),
            {},
            {},
            _build_session_payload(cookies=[], default_headers={}, per_host_headers={}),
        )
    parsed_raw = require_json_object(raw, field_name=field_name)
    invalid = sorted(key for key in parsed_raw if key not in _SESSION_ALLOWED_KEYS)
    if invalid:
        raise MCPToolError(-32602, f"{field_name} received unknown key(s): {', '.join(invalid)}")
    cookies_raw = parsed_raw.get("cookies")
    default_headers_raw = parsed_raw.get("default_headers")
    per_host_headers_raw = parsed_raw.get("per_host_headers")

    default_headers = _parse_headers_dict(
        default_headers_raw,
        field_name=f"{field_name}.default_headers",
    )
    per_host_headers = _parse_per_host_headers(
        per_host_headers_raw,
        field_name=f"{field_name}.per_host_headers",
    )

    cookies = parse_session_cookies(
        cookies_raw,
        field_name=f"{field_name}.cookies",
        request_url=request_url,
    )

    normalized_payload = _build_session_payload(
        cookies=serialize_session_cookies(cookies),
        default_headers=default_headers,
        per_host_headers=per_host_headers,
    )
    return (cookies, default_headers, per_host_headers, normalized_payload)


def build_updated_session_payload(
    *,
    previous_session_payload: JSONDict,
    session_cookies: httpx2.Cookies,
    response: httpx2.Response,
) -> JSONDict:
    default_headers = _require_dict_of_strings(
        previous_session_payload.get("default_headers"),
        field_name="session.default_headers",
    )
    per_host_headers = _require_per_host_headers(
        previous_session_payload.get("per_host_headers"),
        field_name="session.per_host_headers",
    )
    for received_response in (*response.history, response):
        session_cookies.extract_cookies(received_response)
    cookie_items = serialize_session_cookies(session_cookies)
    return _build_session_payload(
        cookies=cookie_items,
        default_headers=default_headers,
        per_host_headers=per_host_headers,
    )


def apply_session_headers(
    *,
    url: str,
    session_default_headers: dict[str, str],
    session_per_host_headers: dict[str, dict[str, str]],
    request_headers: dict[str, str],
) -> dict[str, str]:
    host = _host_for_url(url)
    merged: dict[str, str] = {}
    merged.update(session_default_headers)
    if host is not None:
        host_headers = session_per_host_headers.get(host)
        if host_headers is not None:
            merged.update(host_headers)
    merged.update(request_headers)
    return merged


def apply_redirect_session_headers(
    *,
    url: str,
    session_default_headers: dict[str, str],
    session_per_host_headers: dict[str, dict[str, str]],
    request_headers: dict[str, str],
    redirect_headers: httpx2.Headers,
) -> httpx2.Headers:
    merged = httpx2.Headers(redirect_headers)
    request_header_names = {name.lower() for name in request_headers}
    session_header_names = {
        name.lower() for host_headers in session_per_host_headers.values() for name in host_headers
    }
    default_headers_by_name = {
        name.lower(): value for name, value in session_default_headers.items()
    }
    for header_name in session_header_names - request_header_names:
        header_was_forwarded = header_name in merged
        merged.pop(header_name, None)
        default_value = default_headers_by_name.get(header_name)
        if header_was_forwarded and default_value is not None:
            merged[header_name] = default_value
    host = _host_for_url(url)
    host_headers = session_per_host_headers.get(host) if host is not None else None
    if host_headers is not None:
        for header_name, header_value in host_headers.items():
            if header_name.lower() not in request_header_names:
                merged[header_name] = header_value
    return merged


def _parse_headers_dict(raw: JSONValue, *, field_name: str) -> dict[str, str]:
    if raw is None:
        return {}
    return require_string_map(raw, field_name=field_name)


def _parse_per_host_headers(raw: JSONValue, *, field_name: str) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    headers_by_host = require_json_object(raw, field_name=field_name)
    result: dict[str, dict[str, str]] = {}
    for host, headers in headers_by_host.items():
        normalized_host = host.strip().lower()
        if not normalized_host:
            raise MCPToolError(-32602, f"{field_name} keys must be non-empty strings")
        if normalized_host in result:
            raise MCPToolError(-32602, f"{field_name} contains a duplicate host")
        result[normalized_host] = _parse_headers_dict(
            headers,
            field_name=f"{field_name}[{host}]",
        )
    return result


def _host_for_url(url: str) -> str | None:
    normalized = str(url or "").strip()
    if not normalized:
        return None
    parsed = httpx2.URL(normalized)
    host = parsed.host
    if host is None:
        return None
    return str(host).lower()


def _build_session_payload(
    *,
    cookies: list[JSONDict],
    default_headers: dict[str, str],
    per_host_headers: dict[str, dict[str, str]],
) -> JSONDict:
    return {
        "cookies": cookies,
        "default_headers": default_headers,
        "per_host_headers": per_host_headers,
    }


def _require_dict_of_strings(raw: JSONValue, *, field_name: str) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise MCPToolError(-32603, f"Internal error: {field_name} must be an object")
    result: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise MCPToolError(-32603, f"Internal error: {field_name} must map strings to strings")
        result[key] = value
    return result


def _require_per_host_headers(raw: JSONValue, *, field_name: str) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise MCPToolError(-32603, f"Internal error: {field_name} must be an object")
    result: dict[str, dict[str, str]] = {}
    for host, headers in raw.items():
        if not isinstance(host, str):
            raise MCPToolError(-32603, f"Internal error: {field_name} keys must be strings")
        result[host] = _require_dict_of_strings(headers, field_name=f"{field_name}[{host}]")
    return result
