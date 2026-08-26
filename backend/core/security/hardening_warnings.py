"""SoAI - Configuration security hardening findings [backend/core/security/hardening_warnings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
from collections.abc import Sequence
from urllib.parse import urlsplit

from core.config.protocols import ConfigProtocol
from core.network.hosts import is_bind_all_interfaces_host
from core.runtime.network_policy import is_loopback_host
from core.security.capability_hardening_warnings import (
    collect_capability_hardening_issues,
)
from core.security.hardening_types import SecurityHardeningIssue
from core.security.mcp_server_hardening import collect_mcp_server_hardening_issues

__all__ = (
    "collect_security_hardening_issues",
    "format_security_hardening_warning",
    "is_network_exposure_configured",
)


def _allowed_origins_has_wildcard(config: ConfigProtocol, config_key: str) -> bool:
    allowed_origins = config.get(config_key)
    if allowed_origins is None:
        return False
    if isinstance(allowed_origins, str):
        return allowed_origins.strip() == "*"
    if isinstance(allowed_origins, Sequence):
        for item in allowed_origins:
            if isinstance(item, str) and item.strip() == "*":
                return True
    return False


def _configured_proxy_networks(
    config: ConfigProtocol,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    raw_entries = config.get("SERVER.HTTP.PROXY.TRUSTED_NETWORKS")
    if isinstance(raw_entries, list | tuple | set):
        candidates = tuple(raw_entries)
    else:
        candidates = ()
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in candidates:
        if not isinstance(entry, str) or not entry.strip():
            continue
        try:
            networks.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _proxy_headers_active(config: ConfigProtocol) -> bool:
    return config.get_bool("SERVER.HTTP.PROXY.ENABLE_HEADERS") and bool(
        _configured_proxy_networks(config)
    )


def _proxy_networks_cover_all_addresses(
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    ipv4_networks: list[ipaddress.IPv4Network] = []
    ipv6_networks: list[ipaddress.IPv6Network] = []
    for network in networks:
        if isinstance(network, ipaddress.IPv4Network):
            ipv4_networks.append(network)
        else:
            ipv6_networks.append(network)
    return any(
        network.prefixlen == 0 for network in ipaddress.collapse_addresses(ipv4_networks)
    ) or any(network.prefixlen == 0 for network in ipaddress.collapse_addresses(ipv6_networks))


def _public_origin_is_non_loopback(config: ConfigProtocol) -> bool:
    public_origin = config.get_str("SERVER.PUBLIC_ORIGIN")
    if not public_origin:
        return False
    try:
        host = urlsplit(public_origin).hostname
    except ValueError:
        return False
    return bool(host and not is_loopback_host(host))


def is_network_exposure_configured(config: ConfigProtocol) -> bool:
    if not config.get_bool("SERVER.HTTP.ENABLED"):
        return False
    host = config.get_str("SERVER.HTTP.NETWORK.HOST")
    return (
        bool(host and not is_loopback_host(host))
        or _proxy_headers_active(config)
        or _public_origin_is_non_loopback(config)
    )


def collect_security_hardening_issues(config: ConfigProtocol) -> tuple[SecurityHardeningIssue, ...]:
    issues: list[SecurityHardeningIssue] = []
    http_enabled = config.get_bool("SERVER.HTTP.ENABLED")
    network_exposed = is_network_exposure_configured(config)
    webui_enabled = config.get_bool("SERVER.WEBUI.ENABLED")
    tls_enabled = config.get_bool("SERVER.HTTP.SSL.TLS_ENABLED")
    cookie_secure = config.get_bool("SERVER.WEBUI.COOKIE_SECURE")
    require_secure_transport = config.get_bool("SERVER.HTTP.SECURITY.REQUIRE_SECURE_TRANSPORT")
    proxy_headers_active = _proxy_headers_active(config)
    secure_transport_available = tls_enabled or (proxy_headers_active and require_secure_transport)

    if network_exposed and webui_enabled and not cookie_secure and not secure_transport_available:
        issues.append(
            SecurityHardeningIssue(
                issue_id="webui_cookie_insecure_over_http",
                message=(
                    "WebUI authentication cookies may be transmitted over insecure HTTP. Serve "
                    "SoAI through local TLS or a trusted HTTPS proxy, then require secure "
                    "transport before exposing it."
                ),
                config_keys=(
                    "SERVER.WEBUI.ENABLED",
                    "SERVER.WEBUI.COOKIE_SECURE",
                    "SERVER.HTTP.SECURITY.REQUIRE_SECURE_TRANSPORT",
                    "SERVER.HTTP.SSL.TLS_ENABLED",
                    "SERVER.HTTP.PROXY.ENABLE_HEADERS",
                    "SERVER.HTTP.PROXY.TRUSTED_NETWORKS",
                ),
            ),
        )
    if network_exposed and webui_enabled and cookie_secure and not secure_transport_available:
        issues.append(
            SecurityHardeningIssue(
                issue_id="webui_cookie_secure_but_tls_disabled",
                message=(
                    "SERVER.WEBUI.COOKIE_SECURE is enabled but secure transport is not enforced "
                    "through local TLS or a trusted proxy; HTTP clients cannot complete login."
                ),
                config_keys=(
                    "SERVER.WEBUI.ENABLED",
                    "SERVER.WEBUI.COOKIE_SECURE",
                    "SERVER.HTTP.SSL.TLS_ENABLED",
                    "SERVER.HTTP.SECURITY.REQUIRE_SECURE_TRANSPORT",
                    "SERVER.HTTP.PROXY.ENABLE_HEADERS",
                    "SERVER.HTTP.PROXY.TRUSTED_NETWORKS",
                ),
            ),
        )

    host = config.get_str("SERVER.HTTP.NETWORK.HOST")
    if http_enabled and is_bind_all_interfaces_host(host):
        issues.append(
            SecurityHardeningIssue(
                issue_id="system_api_bind_all_interfaces",
                message=(
                    "SERVER.HTTP.NETWORK.HOST is set to a bind-all address (0.0.0.0/::), "
                    "exposing the System API on all network interfaces."
                ),
                config_keys=("SERVER.HTTP.NETWORK.HOST",),
            ),
        )

    discovery_host = config.get_str("SERVER.HTTP.NETWORK.DISCOVERY_HOST")
    if http_enabled and is_bind_all_interfaces_host(discovery_host):
        issues.append(
            SecurityHardeningIssue(
                issue_id="system_api_discovery_bind_all_interfaces",
                message=(
                    "SERVER.HTTP.NETWORK.DISCOVERY_HOST is set to a bind-all address (0.0.0.0/::), "
                    "exposing discovery endpoints on all network interfaces."
                ),
                config_keys=("SERVER.HTTP.NETWORK.DISCOVERY_HOST",),
            ),
        )

    cors_has_wildcard = _allowed_origins_has_wildcard(
        config,
        "SERVER.HTTP.CORS.ALLOWED_ORIGINS",
    )
    cors_allow_credentials = config.get_bool("SERVER.HTTP.CORS.ALLOW_CREDENTIALS")
    if http_enabled and cors_has_wildcard:
        credentials_note = (
            " (SERVER.HTTP.CORS.ALLOW_CREDENTIALS=true)" if cors_allow_credentials else ""
        )
        issues.append(
            SecurityHardeningIssue(
                issue_id="cors_wildcard_allowed_origins",
                message=(
                    "CORS allowed origins contains a wildcard ('*'), keeping CORS fully open."
                    f"{credentials_note} Replace the wildcard with explicit allowed origins."
                ),
                config_keys=(
                    "SERVER.HTTP.CORS.ALLOWED_ORIGINS",
                    "SERVER.HTTP.CORS.ALLOW_CREDENTIALS",
                ),
            ),
        )

    configured_proxy_networks = _configured_proxy_networks(config)
    if (
        http_enabled
        and config.get_bool("SERVER.HTTP.PROXY.ENABLE_HEADERS")
        and _proxy_networks_cover_all_addresses(configured_proxy_networks)
    ):
        issues.append(
            SecurityHardeningIssue(
                issue_id="trusted_proxy_networks_include_all_addresses",
                message=(
                    "Trusted proxy networks collectively include every address in an IP address "
                    "family while proxy headers are enabled. Restrict trust to explicit proxy "
                    "network ranges."
                ),
                config_keys=(
                    "SERVER.HTTP.PROXY.ENABLE_HEADERS",
                    "SERVER.HTTP.PROXY.TRUSTED_NETWORKS",
                ),
            ),
        )
    if network_exposed and not config.get_bool("API.OPENAI.RATE_LIMITING.ENABLED"):
        issues.append(
            SecurityHardeningIssue(
                issue_id="openai_api_rate_limiting_disabled",
                message=(
                    "OpenAI-compatible and Anthropic-compatible API rate limiting is disabled on "
                    "a network-exposed deployment; abusive clients can exhaust resources."
                ),
                config_keys=("API.OPENAI.RATE_LIMITING.ENABLED",),
            ),
        )
    if (
        network_exposed
        and config.get_bool("TOOLS.MCP.ENABLED")
        and config.get_bool("TOOLS.MCP.SERVER_MODE.ENABLED")
        and _allowed_origins_has_wildcard(
            config,
            "TOOLS.MCP.SERVER_MODE.ALLOWED_ORIGINS",
        )
    ):
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_server_allowed_origins_wildcard",
                message=(
                    "Network-exposed MCP server mode allows every browser origin. Replace the "
                    "wildcard with explicit trusted origins."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.SERVER_MODE.ENABLED",
                    "TOOLS.MCP.SERVER_MODE.ALLOWED_ORIGINS",
                ),
            ),
        )
    issues.extend(
        collect_capability_hardening_issues(
            config,
            network_exposed=network_exposed,
        )
    )
    if network_exposed:
        issues.extend(collect_mcp_server_hardening_issues(config))

    return tuple(issues)


def format_security_hardening_warning(issues: tuple[SecurityHardeningIssue, ...]) -> str:
    if not issues:
        return "Security hardening: no issues detected."
    lines = [
        f"Security hardening: {len(issues)} issue(s) detected. Address these before exposing SoAI:",
    ]
    for issue_number, issue in enumerate(issues, start=1):
        references: list[str] = []
        if issue.config_keys:
            references.append(f"config: {', '.join(issue.config_keys)}")
        if issue.workspace_references:
            references.append(f"workspace: {', '.join(issue.workspace_references)}")
        reference_suffix = f" ({'; '.join(references)})" if references else ""
        lines.append(f"{issue_number}) [{issue.issue_id}] {issue.message}{reference_suffix}")
    return "\n".join(lines)
