"""SoAI - Application state management for FastAPI runtime [backend/features/api/lifecycle/app_state_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress

from fastapi import FastAPI

from features.api.lifecycle.cors_state import CORSStateConfiguration
from features.api.lifecycle.internal_protocols import SecurityRuntimeStateProtocol
from features.api.lifecycle.security_state import SecurityStateConfiguration

__all__ = (
    "apply_cors_state_to_app",
    "apply_security_state_to_app",
    "update_security_runtime_state",
)


def apply_security_state_to_app(app: FastAPI, security_config: SecurityStateConfiguration) -> None:
    app.state.force_https_redirect = security_config.force_https_redirect
    app.state.local_tls_enabled = security_config.local_tls_enabled
    app.state.secure_transport_required = security_config.secure_transport_required
    app.state.trusted_proxy_networks = security_config.trusted_proxy_networks
    app.state.proxy_headers_enabled = security_config.proxy_headers_enabled
    app.state.client_ip_whitelist = security_config.client_ip_whitelist
    app.state.client_ip_blacklist = security_config.client_ip_blacklist
    app.state.security_headers_state = security_config.security_headers_state


def apply_cors_state_to_app(app: FastAPI, cors_config: CORSStateConfiguration) -> None:
    app.state.cors_config = dict(cors_config.cors_config)
    app.state.cors_trusted_origins = cors_config.cors_trusted_origins
    app.state.cors_origin_regex = cors_config.cors_origin_regex
    app.state.cors_max_age = cors_config.cors_max_age


def update_security_runtime_state(
    security_runtime_state: SecurityRuntimeStateProtocol,
    proxy_headers_enabled: bool,
    trusted_proxy_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
    https_redirect_active: bool,
    hsts_enabled: bool,
    content_security_policy: str,
    content_security_policy_insecure: str,
) -> None:
    security_runtime_state.configure(
        proxy_headers_enabled=proxy_headers_enabled,
        trusted_proxy_networks=tuple(str(net) for net in trusted_proxy_networks),
        https_redirect_active=https_redirect_active,
        hsts_enabled=hsts_enabled,
        content_security_policy=content_security_policy,
        content_security_policy_insecure=content_security_policy_insecure,
    )
