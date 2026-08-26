"""SoAI - Outbound URL network policy enforcement [backend/core/network/policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.exceptions import ValidationError
from core.network.dns import resolve_host_ips
from core.network.errors import NetworkPolicyDeniedError, NetworkPolicyResolutionError
from core.network.ip import is_disallowed_ip, is_local_network_ip
from core.network.urls import parse_http_url_host_port

if TYPE_CHECKING:
    from core.network.dns_cache import DnsResolutionCache

__all__ = (
    "enforce_url_local_only_policy",
    "enforce_url_local_only_policy_sync",
    "enforce_url_local_only_policy_ws",
    "enforce_url_network_policy",
    "enforce_url_network_policy_ws",
)


async def enforce_url_network_policy(
    url: str,
    *,
    block_private_networks: bool = True,
    dns_timeout_sec: float = 3.0,
    source: str = "network request",
    dns_cache: DnsResolutionCache | None = None,
) -> str | None:
    if not block_private_networks:
        return None
    normalized_host, port = parse_http_url_host_port(url, infer_https=True)
    if normalized_host in {"localhost", "localhost."}:
        raise NetworkPolicyDeniedError(f"Disallowed hostname for {source}: {normalized_host}")
    try:
        ip_literal = ipaddress.ip_address(normalized_host)
    except ValueError:
        ip_literal = None
    if ip_literal is not None:
        if is_disallowed_ip(ip_literal):
            raise NetworkPolicyDeniedError(f"Disallowed IP address for {source}: {normalized_host}")
        return None
    resolved_ips = await _resolve_policy_host_ips(
        normalized_host,
        port,
        timeout_sec=dns_timeout_sec,
        dns_cache=dns_cache,
    )
    if not resolved_ips:
        raise NetworkPolicyResolutionError(
            f"DNS resolution produced no results for host: {normalized_host}"
        )
    first_valid_ip: str | None = None
    for resolved_ip_text in resolved_ips:
        try:
            resolved_ip = ipaddress.ip_address(resolved_ip_text)
        except ValueError:
            continue
        if is_disallowed_ip(resolved_ip):
            hint = ""
            if resolved_ip.is_unspecified:
                hint = " (DNS sinkhole/misconfiguration likely; check your resolver configuration)"
            raise NetworkPolicyDeniedError(
                f"Disallowed resolved IP address for {source}: {normalized_host} -> {resolved_ip_text}{hint}",
            )
        if first_valid_ip is None:
            first_valid_ip = resolved_ip_text
    return first_valid_ip


async def enforce_url_local_only_policy(
    url: str,
    *,
    dns_timeout_sec: float = 3.0,
    source: str = "network request",
    dns_cache: DnsResolutionCache | None = None,
) -> str | None:
    normalized_host, port = parse_http_url_host_port(url, infer_https=True)
    if normalized_host in {"localhost", "localhost."}:
        return "127.0.0.1"
    try:
        ip_literal = ipaddress.ip_address(normalized_host)
    except ValueError:
        ip_literal = None
    if ip_literal is not None:
        if not is_local_network_ip(ip_literal):
            raise NetworkPolicyDeniedError(f"Disallowed IP address for {source}: {normalized_host}")
        return normalized_host
    resolved_ips = await _resolve_policy_host_ips(
        normalized_host,
        port,
        timeout_sec=dns_timeout_sec,
        dns_cache=dns_cache,
    )
    if not resolved_ips:
        raise NetworkPolicyResolutionError(
            f"DNS resolution produced no results for host: {normalized_host}"
        )
    first_valid_ip: str | None = None
    for resolved_ip_text in resolved_ips:
        try:
            resolved_ip = ipaddress.ip_address(resolved_ip_text)
        except ValueError:
            continue
        if not is_local_network_ip(resolved_ip):
            hint = ""
            if resolved_ip.is_unspecified:
                hint = " (DNS sinkhole/misconfiguration likely; check your resolver configuration)"
            raise NetworkPolicyDeniedError(
                f"Disallowed resolved IP address for {source}: {normalized_host} -> {resolved_ip_text}{hint}",
            )
        if first_valid_ip is None:
            first_valid_ip = resolved_ip_text
    if first_valid_ip is None:
        raise NetworkPolicyResolutionError(
            f"DNS resolution produced no IP addresses for host: {normalized_host}",
        )
    return first_valid_ip


async def _resolve_policy_host_ips(
    normalized_host: str,
    port: int,
    *,
    timeout_sec: float,
    dns_cache: DnsResolutionCache | None,
) -> tuple[str, ...]:
    try:
        return await resolve_host_ips(
            normalized_host,
            port,
            timeout_sec=timeout_sec,
            dns_cache=dns_cache,
        )
    except ValidationError as exception:
        raise NetworkPolicyResolutionError(exception.message) from exception


def enforce_url_local_only_policy_sync(
    url: str,
    *,
    source: str = "network request",
) -> str | None:
    normalized_host, _port = parse_http_url_host_port(url, infer_https=True)
    if normalized_host in {"localhost", "localhost."}:
        return None
    try:
        ip_literal = ipaddress.ip_address(normalized_host)
    except ValueError:
        ip_literal = None
    if ip_literal is not None:
        if not is_local_network_ip(ip_literal):
            raise NetworkPolicyDeniedError(f"Disallowed IP address for {source}: {normalized_host}")
        return normalized_host
    raise ValidationError(
        f"Hostname requires async pinned DNS validation for {source}: {normalized_host}",
    )


async def enforce_url_network_policy_ws(
    url: str,
    *,
    block_private_networks: bool = True,
    dns_timeout_sec: float = 3.0,
    source: str = "network request",
    dns_cache: DnsResolutionCache | None = None,
) -> str | None:
    if not isinstance(url, str):
        raise ValidationError("URL must be a string.")
    try:
        parsed = urlparse(url)
    except (AttributeError, TypeError, ValueError) as exception:
        raise ValidationError(f"URL is invalid: {exception}") from exception
    scheme = (parsed.scheme or "").lower()
    if not scheme and parsed.netloc:
        scheme = "http"
    if scheme in {"ws", "wss"}:
        mapped_scheme = "https" if scheme == "wss" else "http"
        mapped = parsed._replace(scheme=mapped_scheme).geturl()
        return await enforce_url_network_policy(
            mapped,
            block_private_networks=block_private_networks,
            dns_timeout_sec=dns_timeout_sec,
            source=source,
            dns_cache=dns_cache,
        )
    if scheme in {"http", "https"}:
        return await enforce_url_network_policy(
            url,
            block_private_networks=block_private_networks,
            dns_timeout_sec=dns_timeout_sec,
            source=source,
            dns_cache=dns_cache,
        )
    raise ValidationError(f"URL must use http(s) or ws(s) scheme, got: {scheme!r}.")


async def enforce_url_local_only_policy_ws(
    url: str,
    *,
    dns_timeout_sec: float = 3.0,
    source: str = "network request",
    dns_cache: DnsResolutionCache | None = None,
) -> str | None:
    if not isinstance(url, str):
        raise ValidationError("URL must be a string.")
    try:
        parsed = urlparse(url)
    except (AttributeError, TypeError, ValueError) as exception:
        raise ValidationError(f"URL is invalid: {exception}") from exception
    scheme = (parsed.scheme or "").lower()
    if not scheme and parsed.netloc:
        scheme = "http"
    if scheme in {"ws", "wss"}:
        mapped_scheme = "https" if scheme == "wss" else "http"
        mapped = parsed._replace(scheme=mapped_scheme).geturl()
        return await enforce_url_local_only_policy(
            mapped,
            dns_timeout_sec=dns_timeout_sec,
            source=source,
            dns_cache=dns_cache,
        )
    if scheme in {"http", "https"}:
        return await enforce_url_local_only_policy(
            url,
            dns_timeout_sec=dns_timeout_sec,
            source=source,
            dns_cache=dns_cache,
        )
    raise ValidationError(f"URL must use http(s) or ws(s) scheme, got: {scheme!r}.")
