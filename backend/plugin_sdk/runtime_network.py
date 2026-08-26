"""SoAI - Plugin SDK runtime network policy utilities [backend/plugin_sdk/runtime_network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.network_http_client import create_guarded_async_http_client
from core.runtime.network_policy import (
    OfflineModeError,
    enforce_offline_policy,
    get_dns_validation_timeout_sec,
    guard_outbound_http_request,
    is_block_private_network_egress_enabled,
    is_local_network_ip,
    is_local_url,
    is_loopback_host,
    is_offline_mode_enabled,
    require_online_mode,
    validate_local_only_url,
    validate_runtime_host_port,
    validate_runtime_url,
)

__all__ = (
    "OfflineModeError",
    "create_guarded_async_http_client",
    "enforce_offline_policy",
    "is_offline_mode_enabled",
    "guard_outbound_http_request",
    "is_loopback_host",
    "validate_local_only_url",
    "get_dns_validation_timeout_sec",
    "is_block_private_network_egress_enabled",
    "is_local_url",
    "require_online_mode",
    "validate_runtime_host_port",
    "is_local_network_ip",
    "validate_runtime_url",
)
