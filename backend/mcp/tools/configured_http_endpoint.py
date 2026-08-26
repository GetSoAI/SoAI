"""SoAI - MCP configured HTTP endpoint network policy [backend/mcp/tools/configured_http_endpoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.config.numeric_lenient import coerce_lenient_bounded_float
from core.errors.exceptions import ValidationError
from core.network.http_transport import build_pinned_host_extensions
from core.network.policy import (
    enforce_url_local_only_policy,
    enforce_url_network_policy,
)
from core.network.urls import is_local_url, require_absolute_http_url
from core.runtime.network_policy import OfflineModeError
from mcp.tools.error import MCPToolError
from mcp.tools.offline_policy import (
    is_offline_mode_enabled,
    require_url_allowed_when_offline,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "ConfiguredEndpointSpec",
    "ConfiguredEndpointNetworkTarget",
    "resolve_configured_endpoint_from_spec",
    "resolve_configured_endpoint_base_url",
    "resolve_configured_endpoint_network_target",
)


@dataclass(frozen=True, slots=True)
class ConfiguredEndpointNetworkTarget:
    base_url: str
    extensions: dict[str, str] | None


@dataclass(frozen=True, slots=True)
class ConfiguredEndpointSpec:
    config_key: str
    default_base_url: str
    tool_name: str
    capability: str
    config_prefix: str
    local_policy_source: str
    network_blocked_message: str


def resolve_configured_endpoint_base_url(
    *,
    raw_base_url: str,
    default_base_url: str,
    config_key: str,
) -> str:
    try:
        base_url = require_absolute_http_url(str(raw_base_url or default_base_url))
    except ValidationError as exception:
        raise MCPToolError(
            -32602,
            f"{config_key} must be an absolute http or https URL.",
        ) from exception
    while base_url.endswith("/"):
        base_url = base_url[:-1]
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.username is not None or parsed_base_url.password is not None:
        raise MCPToolError(-32602, f"{config_key} must not include credentials.")
    if parsed_base_url.query or parsed_base_url.fragment:
        raise MCPToolError(-32602, f"{config_key} must not include a query string or fragment.")
    return base_url


async def resolve_configured_endpoint_from_spec(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    spec: ConfiguredEndpointSpec,
) -> ConfiguredEndpointNetworkTarget:
    raw_base_url = config.get(spec.config_key, spec.default_base_url)
    base_url = resolve_configured_endpoint_base_url(
        raw_base_url=str(raw_base_url or spec.default_base_url),
        default_base_url=spec.default_base_url,
        config_key=spec.config_key,
    )
    return await resolve_configured_endpoint_network_target(
        config=config,
        runtime_flags=runtime_flags,
        endpoint_base_url=base_url,
        config_key=spec.config_key,
        tool_name=spec.tool_name,
        capability=spec.capability,
        config_prefix=spec.config_prefix,
        local_policy_source=spec.local_policy_source,
        network_blocked_message=spec.network_blocked_message,
    )


def _resolve_request_base_url(
    endpoint_base_url: str,
    pinned_ip: str | None,
) -> ConfiguredEndpointNetworkTarget:
    if pinned_ip is None:
        return ConfiguredEndpointNetworkTarget(base_url=endpoint_base_url, extensions=None)
    parsed = urlparse(endpoint_base_url)
    original_host = parsed.hostname
    if not original_host:
        raise MCPToolError(-32602, "Configured endpoint must include a hostname.")
    return ConfiguredEndpointNetworkTarget(
        base_url=endpoint_base_url,
        extensions=build_pinned_host_extensions(pinned_ip, original_host),
    )


async def _resolve_pinned_local_ip(
    *,
    endpoint_base_url: str,
    dns_timeout_sec: float,
    source: str,
    config_key: str,
) -> str | None:
    parsed_endpoint_url = urlparse(endpoint_base_url)
    if parsed_endpoint_url.scheme.lower() != "http" or is_local_url(endpoint_base_url):
        return None
    try:
        pinned_ip = await enforce_url_local_only_policy(
            endpoint_base_url,
            dns_timeout_sec=dns_timeout_sec,
            source=source,
        )
    except ValidationError as exception:
        raise MCPToolError(
            -32602,
            f"{config_key} must use https unless it targets a local endpoint.",
        ) from exception
    if pinned_ip is None:
        raise MCPToolError(-32602, f"{config_key} must resolve to a local endpoint.")
    return pinned_ip


async def resolve_configured_endpoint_network_target(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    endpoint_base_url: str,
    config_key: str,
    tool_name: str,
    capability: str,
    config_prefix: str,
    local_policy_source: str,
    network_blocked_message: str,
) -> ConfiguredEndpointNetworkTarget:
    try:
        offline_pinned_ip = await require_url_allowed_when_offline(
            runtime_flags,
            tool_name=tool_name,
            url=endpoint_base_url,
            capability=capability,
        )
    except OfflineModeError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
    dns_timeout_sec = coerce_lenient_bounded_float(
        config.get(f"{config_prefix}.DNS_TIMEOUT_SEC"),
        default=5.0,
        minimum=0.5,
        maximum=30.0,
    )
    if offline_pinned_ip is not None:
        return _resolve_request_base_url(endpoint_base_url, offline_pinned_ip)
    pinned_ip = await _resolve_pinned_local_ip(
        endpoint_base_url=endpoint_base_url,
        dns_timeout_sec=dns_timeout_sec,
        source=local_policy_source,
        config_key=config_key,
    )
    if (
        not bool(config.get_bool(f"{config_prefix}.BLOCK_PRIVATE_NETWORK_EGRESS"))
        or is_offline_mode_enabled(runtime_flags)
        or is_local_url(endpoint_base_url)
        or pinned_ip is not None
    ):
        return _resolve_request_base_url(endpoint_base_url, pinned_ip)
    try:
        pinned_ip = await enforce_url_network_policy(
            endpoint_base_url,
            block_private_networks=True,
            dns_timeout_sec=dns_timeout_sec,
            source=tool_name,
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, network_blocked_message) from exception
    return _resolve_request_base_url(endpoint_base_url, pinned_ip)
