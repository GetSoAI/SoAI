"""SoAI - Runtime network policy utilities [backend/core/runtime/network_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress

import httpx2

from core.config.numeric_lenient import coerce_lenient_bounded_float
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import FeatureDisabledError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.dns_cache import DnsResolutionCache
from core.network.hosts import normalize_host
from core.network.ip import is_local_network_ip
from core.network.policy import (
    enforce_url_local_only_policy,
    enforce_url_network_policy,
)
from core.network.urls import build_host_port_url, is_local_url, redact_url_for_logging
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "OfflineModeError",
    "enforce_offline_policy",
    "get_dns_validation_timeout_sec",
    "guard_outbound_http_request",
    "is_block_private_network_egress_enabled",
    "is_local_network_ip",
    "is_local_url",
    "is_loopback_host",
    "is_offline_mode_enabled",
    "require_online_mode",
    "validate_local_only_url",
    "validate_runtime_host_port",
    "validate_runtime_url",
)

LOGGER_NAME = "SoAI.core.runtime.network_policy"
OPERATION_PLUGIN_SDK_RUNTIME_GUARD_OUTBOUND_HTTP_REQUEST = (
    "plugin_sdk.runtime.guard_outbound_http_request"
)
OPERATION_PLUGIN_SDK_RUNTIME_GUARD_OUTBOUND_HTTP_REQUEST_LOCAL_ONLY_POLICY_FAILED = (
    "plugin_sdk.runtime.guard_outbound_http_request.local_only_policy_failed"
)
OPERATION_PLUGIN_SDK_RUNTIME_VALIDATE_LOCAL_ONLY_URL_LOCAL_ONLY_POLICY_FAILED = (
    "plugin_sdk.runtime.validate_local_only_url.local_only_policy_failed"
)

_LOOPBACK_HOSTNAMES = ("localhost", "127.0.0.1", "::1")


class OfflineModeError(FeatureDisabledError): ...


def _offline_mode_message(
    *,
    source: str,
    url: str | None = None,
    details: str | None = None,
) -> str:
    capability = str(source or "network request").strip() or "network request"
    prefix = "SYSTEM.RUNTIME.STAY_OFFLINE is enabled."
    if url is not None and str(url).strip():
        return (
            f"{prefix} {capability} cannot access external resources: {redact_url_for_logging(url)}"
        )
    if details is not None and str(details).strip():
        return f"{prefix} {capability} cannot access external resources: {details}"
    return f"{prefix} {capability} cannot access external resources."


def is_offline_mode_enabled(flags: RuntimeFlagsViewProtocol) -> bool:
    return flags.offline_mode


def is_block_private_network_egress_enabled(flags: RuntimeFlagsViewProtocol) -> bool:
    return flags.block_private_network_egress


def get_dns_validation_timeout_sec(flags: RuntimeFlagsViewProtocol) -> float:
    return coerce_lenient_bounded_float(
        flags.dns_validation_timeout_sec,
        default=3.0,
        minimum=0.1,
        maximum=30.0,
    )


def is_loopback_host(host: str | None) -> bool:
    normalized = normalize_host(host)
    if not normalized:
        return False
    if normalized in _LOOPBACK_HOSTNAMES:
        return True
    try:
        ip_obj = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return ip_obj.is_loopback


async def enforce_offline_policy(
    flags: RuntimeFlagsViewProtocol,
    target_url: str,
    *,
    source: str,
) -> str | None:
    return await validate_local_only_url(flags, target_url, source=source)


def require_online_mode(flags: RuntimeFlagsViewProtocol, *, source: str) -> None:
    if is_offline_mode_enabled(flags):
        raise OfflineModeError(_offline_mode_message(source=source))


async def guard_outbound_http_request(
    flags: RuntimeFlagsViewProtocol,
    request: httpx2.Request,
    *,
    source: str = "http_client",
    dns_cache: DnsResolutionCache | None = None,
) -> str | None:
    logger = get_logger(LOGGER_NAME)
    url_text = ""
    try:
        url_text = str(request.url)
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read request URL while guarding outbound HTTP request (non-critical).",
            operation=OPERATION_PLUGIN_SDK_RUNTIME_GUARD_OUTBOUND_HTTP_REQUEST,
            details={"source": source},
            level="debug",
        )
    if is_offline_mode_enabled(flags):
        if not url_text:
            raise OfflineModeError(
                _offline_mode_message(source=source, details="missing request URL"),
            )
        try:
            return await enforce_url_local_only_policy(
                url_text,
                dns_timeout_sec=get_dns_validation_timeout_sec(flags),
                source=source,
                dns_cache=dns_cache,
            )
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to validate local-only policy while guarding outbound HTTP request.",
                operation=OPERATION_PLUGIN_SDK_RUNTIME_GUARD_OUTBOUND_HTTP_REQUEST_LOCAL_ONLY_POLICY_FAILED,
                details={"source": source, "url": url_text},
            )
            raise OfflineModeError(
                _offline_mode_message(source=source, url=url_text),
            ) from exception
    if is_block_private_network_egress_enabled(flags) and url_text:
        return await enforce_url_network_policy(
            url_text,
            block_private_networks=True,
            dns_timeout_sec=get_dns_validation_timeout_sec(flags),
            source=source,
            dns_cache=dns_cache,
        )
    return None


async def validate_local_only_url(
    flags: RuntimeFlagsViewProtocol,
    url: str,
    *,
    source: str,
    dns_cache: DnsResolutionCache | None = None,
) -> str | None:
    if not is_offline_mode_enabled(flags):
        return None
    try:
        return await enforce_url_local_only_policy(
            url,
            dns_timeout_sec=get_dns_validation_timeout_sec(flags),
            source=source,
            dns_cache=dns_cache,
        )
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        log_exception(
            logger,
            exception,
            message="Failed to validate local-only URL while enforcing offline policy.",
            operation=OPERATION_PLUGIN_SDK_RUNTIME_VALIDATE_LOCAL_ONLY_URL_LOCAL_ONLY_POLICY_FAILED,
            details={"source": source, "url": url},
        )
        raise OfflineModeError(_offline_mode_message(source=source, url=url)) from exception


async def validate_runtime_url(
    flags: RuntimeFlagsViewProtocol,
    url: str,
    *,
    source: str,
    dns_cache: DnsResolutionCache | None = None,
    block_private_networks: bool | None = None,
) -> str | None:
    if is_offline_mode_enabled(flags):
        return await validate_local_only_url(
            flags,
            url,
            source=source,
            dns_cache=dns_cache,
        )
    should_block_private_networks = (
        is_block_private_network_egress_enabled(flags)
        if block_private_networks is None
        else bool(block_private_networks)
    )
    if not should_block_private_networks:
        return None
    return await enforce_url_network_policy(
        url,
        block_private_networks=True,
        dns_timeout_sec=get_dns_validation_timeout_sec(flags),
        source=source,
        dns_cache=dns_cache,
    )


async def validate_runtime_host_port(
    flags: RuntimeFlagsViewProtocol,
    *,
    host: str,
    port: int,
    source: str,
    scheme: str = "https",
    dns_cache: DnsResolutionCache | None = None,
    block_private_networks: bool | None = None,
) -> str | None:
    synthetic_url = build_host_port_url(scheme, host, port)
    return await validate_runtime_url(
        flags,
        synthetic_url,
        source=source,
        dns_cache=dns_cache,
        block_private_networks=block_private_networks,
    )
