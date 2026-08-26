"""SoAI - Security state configuration logic for API lifecycle [backend/features/api/lifecycle/security_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.logging.trace import get_logger
from features.api.middleware.security.networks import parse_network_entries
from features.api.middleware.security_headers import SecurityHeadersMiddleware

__all__ = (
    "SecurityStateConfiguration",
    "compute_ip_filter_configuration",
    "compute_proxy_header_configuration",
    "compute_security_headers_configuration",
    "configure_security_state",
)

LOGGER_NAME = "SoAI.features.api.security_state"


@dataclass(frozen=True, slots=True)
class SecurityStateConfiguration:
    force_https_redirect: bool
    local_tls_enabled: bool
    secure_transport_required: bool
    trusted_proxy_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    proxy_headers_enabled: bool
    client_ip_whitelist: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    client_ip_blacklist: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    security_headers_state: SecurityHeadersMiddleware.ConfigState
    hsts_enabled: bool
    content_security_policy: str
    content_security_policy_insecure: str


def compute_proxy_header_configuration(
    config_obj: ConfigProtocol,
) -> tuple[bool, tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]]:
    has_proxy_headers_enabled = bool(config_obj.get_bool("SERVER.HTTP.PROXY.ENABLE_HEADERS"))
    trusted_proxy_entries_raw = config_obj.get("SERVER.HTTP.PROXY.TRUSTED_NETWORKS", [])
    if isinstance(trusted_proxy_entries_raw, list | tuple | set):
        trusted_proxy_entries = [
            str(entry).strip() for entry in trusted_proxy_entries_raw if str(entry).strip()
        ]
    else:
        trusted_proxy_entries = []
    trusted_proxy_networks = parse_network_entries(
        trusted_proxy_entries,
        error_label="trusted proxy entry",
    )
    if has_proxy_headers_enabled and (not trusted_proxy_networks):
        get_logger(LOGGER_NAME).warning(
            "SERVER.HTTP.PROXY.ENABLE_HEADERS is true but no TRUSTED_NETWORKS are configured. Proxy headers support remains disabled.",
        )
        has_proxy_headers_enabled = False
    if not has_proxy_headers_enabled and trusted_proxy_networks:
        get_logger(LOGGER_NAME).warning(
            "SERVER.HTTP.PROXY.TRUSTED_NETWORKS is set but proxy headers are disabled. These entries will be ignored.",
        )
    proxy_headers_active = has_proxy_headers_enabled and bool(trusted_proxy_networks)
    result_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
        trusted_proxy_networks if proxy_headers_active else ()
    )
    return proxy_headers_active, result_networks


def compute_ip_filter_configuration(
    config_obj: ConfigProtocol,
) -> tuple[
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
]:
    whitelist_entries_raw = config_obj.get("SERVER.HTTP.ACCESS_CONTROL.IP_WHITELIST", [])
    blacklist_entries_raw = config_obj.get("SERVER.HTTP.ACCESS_CONTROL.IP_BLACKLIST", [])
    if isinstance(whitelist_entries_raw, list | tuple | set):
        whitelist_entries = [
            str(entry).strip() for entry in whitelist_entries_raw if str(entry).strip()
        ]
    else:
        whitelist_entries = []
    if isinstance(blacklist_entries_raw, list | tuple | set):
        blacklist_entries = [
            str(entry).strip() for entry in blacklist_entries_raw if str(entry).strip()
        ]
    else:
        blacklist_entries = []
    client_ip_whitelist = parse_network_entries(
        whitelist_entries,
        error_label="SERVER.HTTP.ACCESS_CONTROL.IP_WHITELIST entry",
    )
    client_ip_blacklist = parse_network_entries(
        blacklist_entries,
        error_label="SERVER.HTTP.ACCESS_CONTROL.IP_BLACKLIST entry",
    )
    return client_ip_whitelist, client_ip_blacklist


def compute_security_headers_configuration(
    config_obj: ConfigProtocol,
    existing_state: SecurityHeadersMiddleware.ConfigState | None,
) -> SecurityHeadersMiddleware.ConfigState:
    enforce_hsts = bool(config_obj.get_bool("SERVER.HTTP.SECURITY.ENFORCE_HSTS"))
    upgrade_header_override = config_obj.get(
        "SERVER.HTTP.SECURITY.ENFORCE_UPGRADE_INSECURE_REQUESTS"
    )
    if upgrade_header_override is None:
        upgrade_insecure_requests_enabled = bool(enforce_hsts)
    else:
        upgrade_insecure_requests_enabled = bool(upgrade_header_override)
    security_headers_state = SecurityHeadersMiddleware.configure_state(
        existing_state,
        hsts_enabled=enforce_hsts,
        upgrade_insecure_requests=upgrade_insecure_requests_enabled,
    )
    return security_headers_state


def configure_security_state(
    config_obj: ConfigProtocol,
    existing_security_headers_state: SecurityHeadersMiddleware.ConfigState | None,
) -> SecurityStateConfiguration:
    secure_transport_required = config_obj.get_bool("SERVER.HTTP.SECURITY.REQUIRE_SECURE_TRANSPORT")
    force_https_redirect = config_obj.get_bool("SERVER.HTTP.SECURITY.FORCE_HTTPS_REDIRECT")
    local_tls_enabled = config_obj.get_bool("SERVER.HTTP.SSL.TLS_ENABLED")
    proxy_headers_active, trusted_proxy_networks = compute_proxy_header_configuration(config_obj)
    redirect_active = force_https_redirect and (local_tls_enabled or proxy_headers_active)
    if proxy_headers_active:
        get_logger(LOGGER_NAME).info(
            "Trusted proxy networks configured: %s",
            [str(net) for net in trusted_proxy_networks],
        )
    if force_https_redirect and (not redirect_active):
        get_logger(LOGGER_NAME).warning(
            "SERVER.HTTP.SECURITY.FORCE_HTTPS_REDIRECT is enabled but neither local TLS nor trusted proxy headers are active. HTTPS redirects remain disabled.",
        )
    client_ip_whitelist, client_ip_blacklist = compute_ip_filter_configuration(config_obj)
    security_headers_state = compute_security_headers_configuration(
        config_obj,
        existing_security_headers_state,
    )
    enforce_hsts = bool(config_obj.get_bool("SERVER.HTTP.SECURITY.ENFORCE_HSTS"))
    content_security_policy = str(security_headers_state.secure_policy or "")
    content_security_policy_insecure = str(security_headers_state.insecure_policy or "")
    return SecurityStateConfiguration(
        force_https_redirect=redirect_active,
        local_tls_enabled=local_tls_enabled,
        secure_transport_required=secure_transport_required,
        trusted_proxy_networks=trusted_proxy_networks,
        proxy_headers_enabled=proxy_headers_active,
        client_ip_whitelist=client_ip_whitelist,
        client_ip_blacklist=client_ip_blacklist,
        security_headers_state=security_headers_state,
        hsts_enabled=enforce_hsts,
        content_security_policy=content_security_policy,
        content_security_policy_insecure=content_security_policy_insecure,
    )
