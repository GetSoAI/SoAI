"""SoAI - Browser MCP URL and egress security policy [backend/mcp/tools/browser/security_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.exceptions import FeatureDisabledError, ValidationError
from core.network.hosts import normalize_host
from core.network.policy import (
    enforce_url_local_only_policy_ws,
    enforce_url_network_policy,
    enforce_url_network_policy_ws,
)
from core.runtime.network_policy import is_offline_mode_enabled, validate_local_only_url
from mcp.tools.browser.config_values import resolve_browser_dns_timeout_sec
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.config.protocols import ConfigProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "enforce_browser_http_egress_policy",
    "enforce_browser_navigation_policy",
    "enforce_browser_request_policy",
    "enforce_browser_websocket_policy",
    "require_browser_page_output_allowed",
)

_ALLOWED_DIRECT_NAVIGATION_SCHEMES: frozenset[str] = frozenset({"data"})
_ALLOWED_RENDER_ONLY_SCHEMES: frozenset[str] = frozenset({"blob", "data"})
_LOOPBACK_HOSTNAMES: frozenset[str] = frozenset({"localhost", "localhost."})
_LOOPBACK_PINNED_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1"})
_NETWORK_SCHEMES: frozenset[str] = frozenset({"http", "https"})
_OUTPUT_URL_VALIDATION_ATTEMPTS = 3
_WEBSOCKET_SCHEMES: frozenset[str] = frozenset({"ws", "wss"})


def _scheme(url: str) -> str:
    return (urlparse(url).scheme or "").strip().lower()


def _is_about_blank(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.scheme or "").lower() == "about" and (parsed.path or "").lower() == "blank"


def _is_browser_render_only_url_allowed(url: str) -> bool:
    scheme = _scheme(url)
    return scheme in _ALLOWED_RENDER_ONLY_SCHEMES or _is_about_blank(url)


def _is_browser_direct_navigation_allowed(url: str) -> bool:
    scheme = _scheme(url)
    return scheme in _ALLOWED_DIRECT_NAVIGATION_SCHEMES or _is_about_blank(url)


def _normalized_url_host(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = normalize_host(parsed.hostname)
    except (AttributeError, TypeError, ValueError) as exception:
        raise ValidationError(f"Browser WebSocket URL is invalid: {exception}") from exception
    if host is None:
        raise ValidationError("Browser WebSocket URL must include a hostname.")
    return host


def _require_websocket_dns_pin_supported(url: str, pinned_host: str | None) -> None:
    if pinned_host is None:
        return
    request_host = _normalized_url_host(url)
    normalized_pinned_host = normalize_host(pinned_host)
    if normalized_pinned_host is None:
        raise ValidationError("Browser WebSocket DNS validation returned an invalid host.")
    if request_host == normalized_pinned_host:
        return
    if request_host in _LOOPBACK_HOSTNAMES and normalized_pinned_host in _LOOPBACK_PINNED_HOSTS:
        return
    raise ValidationError(
        "Browser WebSocket requests to hostnames that require DNS pinning are blocked.",
    )


def _raise_unsupported_url(tool_name: str, url: str) -> None:
    scheme = _scheme(url)
    raise MCPToolError(
        -32602,
        f"{tool_name} does not allow browser navigation or output for URL scheme: {scheme!r}.",
        data={"reason": "browser_url_scheme_blocked"},
    )


async def enforce_browser_http_egress_policy(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    url: str,
    source: str,
) -> str | None:
    dns_timeout_sec = resolve_browser_dns_timeout_sec(config)
    if is_offline_mode_enabled(runtime_flags):
        return await validate_local_only_url(runtime_flags, url, source=source)
    return await enforce_url_network_policy(
        url,
        block_private_networks=True,
        dns_timeout_sec=dns_timeout_sec,
        source=source,
    )


async def enforce_browser_navigation_policy(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    url: str,
    source: str,
) -> None:
    scheme = _scheme(url)
    if scheme in _NETWORK_SCHEMES:
        try:
            await enforce_browser_http_egress_policy(
                config,
                runtime_flags,
                url=url,
                source=source,
            )
        except (FeatureDisabledError, ValidationError) as exception:
            raise MCPToolError(-32602, str(exception)) from exception
        return
    if _is_browser_direct_navigation_allowed(url):
        return
    _raise_unsupported_url("browser_navigate", url)


async def enforce_browser_request_policy(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    url: str,
    source: str,
) -> None:
    scheme = _scheme(url)
    if scheme in _NETWORK_SCHEMES:
        await enforce_browser_http_egress_policy(
            config,
            runtime_flags,
            url=url,
            source=source,
        )
        return
    if _is_browser_render_only_url_allowed(url):
        return
    raise ValidationError(f"Disallowed browser request URL scheme for {source}: {scheme!r}")


async def enforce_browser_websocket_policy(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    url: str,
    source: str,
) -> str | None:
    scheme = _scheme(url)
    if scheme not in _WEBSOCKET_SCHEMES:
        raise ValidationError(f"Disallowed browser WebSocket URL scheme for {source}: {scheme!r}")
    dns_timeout_sec = resolve_browser_dns_timeout_sec(config)
    if is_offline_mode_enabled(runtime_flags):
        pinned_host = await enforce_url_local_only_policy_ws(
            url,
            dns_timeout_sec=dns_timeout_sec,
            source=source,
        )
        _require_websocket_dns_pin_supported(url, pinned_host)
        return pinned_host
    pinned_host = await enforce_url_network_policy_ws(
        url,
        block_private_networks=True,
        dns_timeout_sec=dns_timeout_sec,
        source=source,
    )
    _require_websocket_dns_pin_supported(url, pinned_host)
    return pinned_host


async def _require_browser_output_url_allowed(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    current_url: str,
    tool_name: str,
) -> None:
    scheme = _scheme(current_url)
    if scheme in _NETWORK_SCHEMES:
        try:
            await enforce_browser_http_egress_policy(
                utility_tools.config,
                utility_tools.runtime_flags,
                url=current_url,
                source=f"MCP {tool_name} page output",
            )
        except (FeatureDisabledError, ValidationError) as exception:
            raise MCPToolError(-32603, str(exception)) from exception
        return
    if _is_browser_render_only_url_allowed(current_url):
        return
    _raise_unsupported_url(tool_name, current_url)


async def require_browser_page_output_allowed(
    utility_tools: MCPUtilityToolsProtocol,
    page: Page,
    *,
    tool_name: str,
) -> str:
    remaining_attempts = _OUTPUT_URL_VALIDATION_ATTEMPTS
    while remaining_attempts > 0:
        remaining_attempts -= 1
        current_url = str(page.url or "").strip()
        await _require_browser_output_url_allowed(
            utility_tools,
            current_url=current_url,
            tool_name=tool_name,
        )
        if str(page.url or "").strip() == current_url:
            return current_url
    raise MCPToolError(
        -32603,
        "Browser page changed URL during output policy validation. Retry after navigation settles.",
        data={"reason": "browser_output_url_unstable"},
    )
