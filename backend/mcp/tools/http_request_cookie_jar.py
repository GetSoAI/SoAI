"""SoAI - HTTP request cookie jar persistence [backend/mcp/tools/http_request_cookie_jar.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from http.cookiejar import Cookie, CookieJar, DefaultCookiePolicy
from typing import TYPE_CHECKING, override
from urllib.parse import urlsplit
from urllib.request import Request

import httpx2

from mcp.tools.argument_fields import require_json_object
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("parse_session_cookies", "serialize_session_cookies")

_COOKIE_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "value",
        "domain",
        "path",
        "secure",
        "expires_at",
        "host_only",
        "http_only",
        "same_site",
    }
)


class _HostOnlyCookiePolicy(DefaultCookiePolicy):
    @override
    def return_ok(self, cookie: Cookie, request: Request) -> bool:
        hostname = urlsplit(request.full_url).hostname or ""
        if not cookie.domain_specified and cookie.domain.lower() != hostname.lower():
            return False
        return super().return_ok(cookie, request)


def parse_session_cookies(
    raw: JSONValue,
    *,
    field_name: str,
    request_url: str,
) -> httpx2.Cookies:
    request_hostname = _host_for_url(request_url)
    if request_hostname is None:
        raise MCPToolError(-32602, "Session request URL must include a hostname")
    cookies = httpx2.Cookies(CookieJar(policy=_HostOnlyCookiePolicy()))
    for cookie_payload in _parse_cookie_list(raw, field_name=field_name):
        cookies.jar.set_cookie(
            _cookie_from_payload(cookie_payload, request_hostname=request_hostname)
        )
    return cookies


def serialize_session_cookies(cookies: httpx2.Cookies) -> list[JSONDict]:
    items: dict[tuple[str, str, str], JSONDict] = {}
    for cookie in cookies.jar:
        name = str(cookie.name)
        value = str(cookie.value)
        domain = str(cookie.domain or "")
        path = str(cookie.path or "")
        key = (name, domain, path)
        payload_item: JSONDict = {
            "name": name,
            "value": value,
            "secure": bool(cookie.secure),
            "host_only": not bool(cookie.domain_specified),
            "http_only": bool(cookie.has_nonstandard_attr("HttpOnly")),
        }
        if domain:
            payload_item["domain"] = domain
        if path:
            payload_item["path"] = path
        if cookie.expires is not None:
            payload_item["expires_at"] = int(cookie.expires)
        same_site = cookie.get_nonstandard_attr("SameSite")
        if isinstance(same_site, str) and same_site:
            payload_item["same_site"] = same_site
        items[key] = payload_item
    return [items[key] for key in sorted(items.keys())]


def _parse_cookie_list(raw: JSONValue, *, field_name: str) -> list[JSONDict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise MCPToolError(-32602, f"{field_name} must be an array")
    cookies: list[JSONDict] = []
    for index, item in enumerate(raw):
        cookie_item = require_json_object(item, field_name=f"{field_name}[{index}]")
        invalid = sorted(key for key in cookie_item if key not in _COOKIE_ALLOWED_KEYS)
        if invalid:
            raise MCPToolError(
                -32602,
                f"{field_name}[{index}] received unknown key(s): {', '.join(invalid)}",
            )
        name_raw = cookie_item.get("name")
        value_raw = cookie_item.get("value")
        if not isinstance(name_raw, str) or not name_raw.strip():
            raise MCPToolError(-32602, f"{field_name}[{index}].name must be a non-empty string")
        if not isinstance(value_raw, str):
            raise MCPToolError(-32602, f"{field_name}[{index}].value must be a string")
        cookie: JSONDict = {"name": name_raw, "value": value_raw}
        _parse_cookie_domain(cookie_item, cookie, field_name=f"{field_name}[{index}]")
        _parse_cookie_path(cookie_item, cookie, field_name=f"{field_name}[{index}]")
        for key in ("secure", "host_only", "http_only"):
            _parse_optional_cookie_bool(
                cookie_item,
                cookie,
                key=key,
                field_name=f"{field_name}[{index}].{key}",
            )
        _parse_cookie_expiry(cookie_item, cookie, field_name=f"{field_name}[{index}]")
        _parse_cookie_same_site(cookie_item, cookie, field_name=f"{field_name}[{index}]")
        cookies.append(cookie)
    return cookies


def _parse_cookie_domain(source: JSONDict, target: JSONDict, *, field_name: str) -> None:
    value = source.get("domain")
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise MCPToolError(-32602, f"{field_name}.domain must be a non-empty string")
    target["domain"] = value


def _parse_cookie_path(source: JSONDict, target: JSONDict, *, field_name: str) -> None:
    value = source.get("path")
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise MCPToolError(-32602, f"{field_name}.path must be a non-empty string")
    target["path"] = value


def _parse_optional_cookie_bool(
    source: JSONDict,
    target: JSONDict,
    *,
    key: str,
    field_name: str,
) -> None:
    value = source.get(key)
    if value is None:
        return
    if not isinstance(value, bool):
        raise MCPToolError(-32602, f"{field_name} must be a boolean")
    target[key] = value


def _parse_cookie_expiry(source: JSONDict, target: JSONDict, *, field_name: str) -> None:
    value = source.get("expires_at")
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise MCPToolError(-32602, f"{field_name}.expires_at must be an integer")
    target["expires_at"] = value


def _parse_cookie_same_site(source: JSONDict, target: JSONDict, *, field_name: str) -> None:
    value = source.get("same_site")
    if value is None:
        return
    if not isinstance(value, str) or value.lower() not in {"lax", "strict", "none"}:
        raise MCPToolError(-32602, f"{field_name}.same_site must be lax, strict, or none")
    target["same_site"] = value.capitalize()


def _host_for_url(url: str) -> str | None:
    normalized = str(url or "").strip()
    if not normalized:
        return None
    parsed = httpx2.URL(normalized)
    return str(parsed.host).lower() if parsed.host is not None else None


def _cookie_from_payload(payload: JSONDict, *, request_hostname: str) -> Cookie:
    name = str(payload["name"])
    value = str(payload["value"])
    path = str(payload.get("path") or "/")
    domain_value = payload.get("domain")
    domain = str(domain_value) if isinstance(domain_value, str) else request_hostname
    host_only_value = payload.get("host_only")
    host_only = (
        True
        if not isinstance(domain_value, str)
        else host_only_value if isinstance(host_only_value, bool) else False
    )
    if host_only and domain.lower() != request_hostname:
        raise MCPToolError(-32602, "Host-only session cookie domain must match the request host")
    secure_value = payload.get("secure")
    secure = secure_value if isinstance(secure_value, bool) else False
    expires_value = payload.get("expires_at")
    expires = (
        expires_value
        if isinstance(expires_value, int) and not isinstance(expires_value, bool)
        else None
    )
    rest: dict[str, str] = {}
    if payload.get("http_only") is True:
        rest["HttpOnly"] = ""
    same_site = payload.get("same_site")
    if isinstance(same_site, str):
        rest["SameSite"] = same_site
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=not host_only,
        domain_initial_dot=not host_only and domain.startswith("."),
        path=path,
        path_specified=True,
        secure=secure,
        expires=expires,
        discard=expires is None,
        comment=None,
        comment_url=None,
        rest=rest,
        rfc2109=False,
    )
