"""SoAI - DNS resolution helpers for network policy [backend/core/network/dns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import TYPE_CHECKING

from dns.exception import DNSException, Timeout
from dns.resolver import NXDOMAIN, NoAnswer, NoNameservers, Resolver

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    BoundedBlockingTimeoutBase,
    BoundedThreadPoolConfig,
    create_bounded_thread_pool_from_env,
    run_bounded_blocking_call,
)
from core.concurrency.bounded_pool_lifecycle import (
    resolve_lazy_bounded_pool,
    shutdown_lazy_bounded_pool,
)
from core.concurrency.ephemeral_tasks import spawn_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.network.dns_cache import DnsResolutionCache

    type GetAddrInfoSockAddr = tuple[str, int] | tuple[str, int, int, int] | tuple[int, bytes]
    type GetAddrInfoEntry = tuple[
        socket.AddressFamily,
        socket.SocketKind,
        int,
        str,
        GetAddrInfoSockAddr,
    ]
    type GetAddrInfoResult = list[GetAddrInfoEntry]

__all__ = (
    "configure_dns_override_servers",
    "resolve_host_ips",
    "shutdown_dns_executor",
)

LOGGER_NAME = "SoAI.core.network.dns"
OPERATION_CORE_NETWORK_DNS_AWAIT_TIMED_OUT_FUTURE_WAIT = (
    "core.network.dns.await_timed_out_future.wait"
)
OPERATION_CORE_NETWORK_DNS_AWAIT_TIMED_OUT_FUTURE_WAIT_CANCELLED = (
    "core.network.dns.await_timed_out_future.wait_cancelled"
)


class DnsExecutorState:
    executor: BoundedBlockingPool | None = None
    override_nameservers: tuple[str, ...] | None = None


async def _await_timed_out_dns_future[Result](in_flight: asyncio.Future[Result]) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        shielded = asyncio.shield(in_flight)
        try:
            await shielded
        except asyncio.CancelledError as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="core.network.dns.await_timed_out_future.wait_cancelled",
            )
            log_handled_exception(
                logger,
                coerced,
                message=(
                    "Deferred DNS timeout cleanup observed cancellation while awaiting "
                    "in-flight resolution (non-critical)."
                ),
                operation=OPERATION_CORE_NETWORK_DNS_AWAIT_TIMED_OUT_FUTURE_WAIT_CANCELLED,
                level="debug",
            )
            return
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        socket.gaierror,
        DNSException,
    ) as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="core.network.dns.await_timed_out_future.wait",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed while awaiting in-flight DNS resolution after timeout (non-critical).",
            operation=OPERATION_CORE_NETWORK_DNS_AWAIT_TIMED_OUT_FUTURE_WAIT,
            level="debug",
        )


def configure_dns_override_servers(servers: tuple[str, ...] | None) -> None:
    DnsExecutorState.override_nameservers = servers


def _create_dns_executor() -> BoundedBlockingPool:
    return create_bounded_thread_pool_from_env(
        BoundedThreadPoolConfig(
            label="dns_resolution",
            thread_name_prefix="soai-dns",
            max_workers_env="SOAI_DNS_MAX_WORKERS",
            max_in_flight_env="SOAI_DNS_MAX_IN_FLIGHT",
            default_max_workers=4,
            minimum_workers=1,
            maximum_workers=64,
            default_in_flight_multiplier=2,
            default_min_in_flight=8,
            max_in_flight_limit=2048,
        ),
    )


def _get_dns_executor() -> BoundedBlockingPool:
    executor = resolve_lazy_bounded_pool(DnsExecutorState.executor, _create_dns_executor)
    DnsExecutorState.executor = executor
    return executor


def _canonicalize_dns_hostname(host: str) -> str:
    candidate = host.strip().lower()
    if not candidate:
        raise ValidationError("host is required.")
    try:
        normalized = candidate.encode("idna").decode("ascii")
    except UnicodeError as exception:
        raise ValidationError(f"DNS resolution failed for host: {candidate}") from exception
    return normalized.lower()


async def resolve_host_ips(
    host: str,
    port: int,
    *,
    timeout_sec: float = 3.0,
    dns_cache: DnsResolutionCache | None = None,
) -> tuple[str, ...]:
    normalized_host = str(host or "").strip()
    if not normalized_host:
        raise ValidationError("host is required.")
    if normalized_host.startswith("[") and normalized_host.endswith("]"):
        normalized_host = normalized_host[1:-1].strip()
    try:
        ip_literal = ipaddress.ip_address(normalized_host)
    except ValueError:
        ip_literal = None
    if ip_literal is not None:
        return (str(ip_literal),)
    canonical_host = _canonicalize_dns_hostname(normalized_host)
    if dns_cache is not None:
        cached_result = dns_cache.get(canonical_host, port)
        if cached_result is not None:
            return cached_result

    result: tuple[str, ...] = ()

    def _extract_resolved_ips(addrinfo: GetAddrInfoResult) -> tuple[str, ...]:
        resolved: list[str] = []
        for family, _socktype, _proto, _canonname, sockaddr in addrinfo:
            _ = (_socktype, _proto, _canonname)
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue
            if not isinstance(sockaddr, tuple) or len(sockaddr) < 2:
                continue
            ip_value = sockaddr[0]
            if isinstance(ip_value, bytes):
                try:
                    ip_text = ip_value.decode("utf-8")
                except UnicodeDecodeError:
                    continue
            elif isinstance(ip_value, str):
                ip_text = ip_value
            else:
                continue
            normalized_ip = ip_text.strip()
            if normalized_ip:
                resolved.append(normalized_ip)
        return tuple(dict.fromkeys(resolved))

    override = DnsExecutorState.override_nameservers
    executor = _get_dns_executor()
    if override:

        def _blocking_resolve_with_override() -> tuple[str, ...]:
            resolved: list[str] = []
            resolver = Resolver(configure=False)
            resolver.nameservers = list(override)
            resolver.lifetime = float(timeout_sec)
            for rdtype in ("A", "AAAA"):
                try:
                    answer = resolver.resolve(canonical_host, rdtype)
                except NXDOMAIN:
                    continue
                except NoAnswer:
                    continue
                except NoNameservers:
                    continue
                except Timeout:
                    continue
                for rdata in answer:
                    try:
                        address = rdata.address
                    except AttributeError:
                        address = None
                    if isinstance(address, str) and address:
                        resolved.append(address)
            return tuple(dict.fromkeys(resolved))

        try:
            result = await run_bounded_blocking_call(
                executor,
                _blocking_resolve_with_override,
                timeout_sec=timeout_sec,
                on_timeout=lambda future: spawn_ephemeral_task(
                    _await_timed_out_dns_future(future),
                    name="dns-timeout-cleanup",
                ),
            )
        except BoundedBlockingTimeoutBase as exception:
            raise ValidationError(
                f"DNS resolution timed out after {timeout_sec:.1f}s for host: {normalized_host}",
            ) from exception
        except (DNSException, OSError, RuntimeError, TypeError, ValueError) as exception:
            raise ValidationError(
                f"DNS resolution failed for host: {canonical_host}",
            ) from exception
    else:

        def _blocking_getaddrinfo() -> GetAddrInfoResult:
            return socket.getaddrinfo(canonical_host, port, type=socket.SOCK_STREAM)

        try:
            addrinfo = await run_bounded_blocking_call(
                executor,
                _blocking_getaddrinfo,
                timeout_sec=timeout_sec,
                on_timeout=lambda future: spawn_ephemeral_task(
                    _await_timed_out_dns_future(future),
                    name="dns-timeout-cleanup",
                ),
            )
        except BoundedBlockingTimeoutBase as exception:
            raise ValidationError(
                f"DNS resolution timed out after {timeout_sec:.1f}s for host: {normalized_host}",
            ) from exception
        except (socket.gaierror, UnicodeError) as exception:
            raise ValidationError(
                f"DNS resolution failed for host: {canonical_host}",
            ) from exception

        result = _extract_resolved_ips(addrinfo)
        if not result:
            raise ValidationError(f"DNS resolution failed for host: {canonical_host}")

    if not result:
        raise ValidationError(f"DNS resolution failed for host: {canonical_host}")

    if dns_cache is not None:
        dns_cache.put(canonical_host, port, result)

    return result


def shutdown_dns_executor() -> None:
    executor = DnsExecutorState.executor
    shutdown_lazy_bounded_pool(executor)
    DnsExecutorState.executor = None
