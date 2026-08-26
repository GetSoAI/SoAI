"""SoAI - Guarded runtime HTTP client construction [backend/core/runtime/network_http_client.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from http.cookiejar import Cookie, CookieJar, DefaultCookiePolicy
from typing import override
from urllib.request import Request

import httpx2

from core.network.dns_cache import DnsResolutionCache
from core.network.http_transport import PinnedHost, PolicyPinnedAsyncHTTPTransport
from core.network.outbound_http_profiles import build_outbound_request_headers
from core.runtime.network_policy import guard_outbound_http_request
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("create_guarded_async_http_client",)


class _RejectAmbientCookiesPolicy(DefaultCookiePolicy):
    @override
    def set_ok(self, cookie: Cookie, request: Request) -> bool:
        _ = cookie, request
        return False


def create_guarded_async_http_client(
    flags: RuntimeFlagsViewProtocol,
    *,
    source: str,
    timeout: httpx2.Timeout | float | None = None,
    limits: httpx2.Limits | None = None,
    trust_env: bool = False,
    dns_cache: DnsResolutionCache | None = None,
    default_headers: dict[str, str] | None = None,
) -> httpx2.AsyncClient:
    effective_dns_cache = dns_cache or DnsResolutionCache(ttl_seconds=60.0, max_entries=1024)
    effective_limits = limits or httpx2.Limits()

    async def request_pinner(request: httpx2.Request) -> PinnedHost | None:
        pinned_ip = await guard_outbound_http_request(
            flags,
            request,
            source=source,
            dns_cache=effective_dns_cache,
        )
        if not pinned_ip:
            return None
        original_host = request.url.host or ""
        if not original_host:
            return None
        return PinnedHost(pinned_ip=pinned_ip, original_host=original_host)

    transport = PolicyPinnedAsyncHTTPTransport(
        request_pinner=request_pinner,
        limits=effective_limits,
        trust_env=trust_env,
    )
    return httpx2.AsyncClient(
        headers=(
            default_headers
            if default_headers is not None
            else build_outbound_request_headers(profile_type="neutral_runtime")
        ),
        timeout=timeout,
        limits=effective_limits,
        cookies=CookieJar(policy=_RejectAmbientCookiesPolicy()),
        transport=transport,
        trust_env=trust_env,
    )
