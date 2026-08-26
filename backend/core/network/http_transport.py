"""SoAI - HTTP transports for network-policy enforced outbound connections [backend/core/network/http_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

import httpx2

from core.errors.exceptions import ValidationError
from core.network.urls import format_host_for_url

__all__ = (
    "PINNED_HOST_IP_EXTENSION",
    "PINNED_HOST_ORIGINAL_EXTENSION",
    "PinnedHost",
    "PolicyPinnedAsyncHTTPTransport",
    "build_pinned_host_extensions",
)

PINNED_HOST_IP_EXTENSION = "soai.pinned_host_ip"
PINNED_HOST_ORIGINAL_EXTENSION = "soai.pinned_host_original"


@dataclass(frozen=True, slots=True)
class PinnedHost:
    pinned_ip: str
    original_host: str


def build_pinned_host_extensions(pinned_ip: str, original_host: str) -> dict[str, str]:
    return {
        PINNED_HOST_IP_EXTENSION: pinned_ip,
        PINNED_HOST_ORIGINAL_EXTENSION: original_host,
    }


def _read_pinned_host_extensions(request: httpx2.Request) -> PinnedHost | None:
    pinned_ip = request.extensions.get(PINNED_HOST_IP_EXTENSION)
    original_host = request.extensions.get(PINNED_HOST_ORIGINAL_EXTENSION)
    if not isinstance(pinned_ip, str) or not pinned_ip.strip():
        return None
    if not isinstance(original_host, str) or not original_host.strip():
        return None
    return PinnedHost(pinned_ip=pinned_ip.strip(), original_host=original_host.strip())


def _clear_pinned_host_extensions(request: httpx2.Request) -> None:
    request.extensions.pop(PINNED_HOST_IP_EXTENSION, None)
    request.extensions.pop(PINNED_HOST_ORIGINAL_EXTENSION, None)


class PolicyPinnedAsyncHTTPTransport(httpx2.AsyncHTTPTransport):

    def __init__(
        self,
        *,
        request_pinner: Callable[[httpx2.Request], Awaitable[PinnedHost | None]],
        limits: httpx2.Limits | None = None,
        trust_env: bool = False,
    ) -> None:
        super().__init__(limits=limits or httpx2.Limits(), trust_env=trust_env)
        self._request_pinner = request_pinner

    @override
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        pinned = _read_pinned_host_extensions(request)
        url = request.url
        if pinned is not None and str(url.host or "").lower() != pinned.original_host.lower():
            pinned = None
            _clear_pinned_host_extensions(request)
        if pinned is None:
            pinned = await self._request_pinner(request)
        if pinned is None:
            return await super().handle_async_request(request)
        if str(url.host or "").lower() != pinned.original_host.lower():
            raise ValidationError("Pinned HTTP request host does not match the request URL.")
        port = url.port or (443 if str(url.scheme) == "https" else 80)
        default_port = 443 if str(url.scheme) == "https" else 80
        host_header = str(request.headers.get("Host") or "")
        if not host_header:
            host_header = format_host_for_url(pinned.original_host)
            if port != default_port:
                host_header = f"{format_host_for_url(pinned.original_host)}:{port}"
        target_url = url.copy_with(host=pinned.pinned_ip, port=port)
        new_headers = httpx2.Headers(request.headers)
        new_headers["Host"] = host_header
        extensions = dict(request.extensions)
        extensions["sni_hostname"] = pinned.original_host
        rewritten = httpx2.Request(
            method=request.method,
            url=target_url,
            headers=new_headers,
            stream=request.stream,
            extensions=extensions,
        )
        return await super().handle_async_request(rewritten)
