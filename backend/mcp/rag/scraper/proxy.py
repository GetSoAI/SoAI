"""SoAI - MCP web scraper proxy management [backend/mcp/rag/scraper/proxy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx2

from core.errors.exception_logging import log_handled_exception
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.http_transport import PinnedHost, PolicyPinnedAsyncHTTPTransport
from core.network.outbound_http_profiles import build_outbound_request_headers
from core.network.urls import replace_url_host
from core.runtime.network_policy import (
    guard_outbound_http_request,
    validate_local_only_url,
)

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol

__all__ = (
    "get_http_client",
    "get_proxy_url",
    "should_bypass_proxy",
)

LOGGER_NAME = "SoAI.mcp.rag.proxy"
OPERATION = "mcp.rag.scraper.proxy.should_bypass_proxy"
_SOCKS_PROXY_SCHEMES = frozenset(("socks4", "socks4a", "socks5", "socks5h"))


def should_bypass_proxy(self: WebContentFetcherProtocol, url: str) -> bool:
    logger = get_logger(LOGGER_NAME)
    if not self.proxy_no_proxy:
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        no_proxy_hosts = [
            host.strip().lower() for host in self.proxy_no_proxy.split(",") if host.strip()
        ]
        return host in no_proxy_hosts
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to parse URL for proxy bypass evaluation (non-critical).",
            operation=OPERATION,
            details={"url": url},
            level="debug",
        )
        return False


def get_proxy_url(self: WebContentFetcherProtocol) -> str | None:
    if not self.proxy_enabled:
        return None
    proxies = self.proxy_list
    if self.proxy_rotation_enabled and proxies:
        index = self.proxy_sequential_index % len(proxies)
        self.set_proxy_sequential_index(self.proxy_sequential_index + 1)
        proxy = proxies[index]
        return proxy
    if self.proxy_socks5:
        return self.proxy_socks5
    if self.proxy_https:
        return self.proxy_https
    if self.proxy_http:
        return self.proxy_http
    return None


def _build_proxy_policy_url(proxy_url: str) -> str:
    parsed = urlparse(proxy_url)
    scheme = (parsed.scheme or "").lower()
    if scheme in _SOCKS_PROXY_SCHEMES:
        return parsed._replace(scheme="http").geturl()
    return proxy_url


@contextlib.asynccontextmanager
async def get_http_client(
    self: WebContentFetcherProtocol,
    url: str = "",
    pinned_ip: str | None = None,
    original_host: str | None = None,
) -> AsyncGenerator[httpx2.AsyncClient]:
    use_proxy = not (url and should_bypass_proxy(self, url))
    proxy_url = get_proxy_url(self) if use_proxy else None
    if proxy_url:
        proxy_pinned_host = await validate_local_only_url(
            self.runtime_flags,
            _build_proxy_policy_url(proxy_url),
            source="mcp_rag_scraper_proxy",
        )
        if proxy_pinned_host:
            proxy_url = replace_url_host(proxy_url, proxy_pinned_host)

    if pinned_ip and original_host and (not proxy_url):

        async def request_pinner(request: httpx2.Request) -> PinnedHost | None:
            request_host = str(request.url.host or "")
            if request_host.lower() == original_host.lower():
                return PinnedHost(pinned_ip=pinned_ip, original_host=original_host)
            next_pinned_ip = await guard_outbound_http_request(
                self.runtime_flags,
                request,
                source="mcp_rag_scraper",
            )
            if not next_pinned_ip or not request_host:
                return None
            return PinnedHost(pinned_ip=next_pinned_ip, original_host=request_host)

        transport = PolicyPinnedAsyncHTTPTransport(request_pinner=request_pinner)
        async with httpx2.AsyncClient(
            headers=build_outbound_request_headers(profile_type="service_api"),
            timeout=self.timeout,
            transport=transport,
            trust_env=False,
        ) as client:
            yield client
            return
    if not proxy_url:
        yield self.http_client
        return

    async def request_guard(request: httpx2.Request) -> None:
        await guard_outbound_http_request(self.runtime_flags, request, source="mcp_rag_scraper")

    async with httpx2.AsyncClient(
        headers=build_outbound_request_headers(profile_type="service_api"),
        timeout=self.timeout,
        proxy=proxy_url,
        event_hooks={"request": [request_guard]},
        trust_env=False,
    ) as client:
        yield client
