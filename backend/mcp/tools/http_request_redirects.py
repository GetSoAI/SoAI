"""SoAI - Request-local HTTP redirect execution [backend/mcp/tools/http_request_redirects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx2

__all__ = ("stream_request_with_local_cookies",)

MAX_HTTP_REDIRECTS = 20


@asynccontextmanager
async def stream_request_with_local_cookies(
    client: httpx2.AsyncClient,
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    content: bytes | None,
    timeout: float,
    follow_redirects: bool,
    cookies: httpx2.Cookies | None,
    extensions: dict[str, str] | None,
    resolve_extensions: Callable[[str], Awaitable[dict[str, str] | None]],
    resolve_headers: Callable[[httpx2.Request], httpx2.Headers],
) -> AsyncGenerator[httpx2.Response]:
    active_method = method
    active_url: httpx2.URL | str = url
    active_headers: httpx2.Headers | dict[str, str] = headers
    active_content = content
    active_extensions = extensions
    last_request: httpx2.Request | None = None
    for _redirect_index in range(MAX_HTTP_REDIRECTS + 1):
        prepared_headers = httpx2.Headers(active_headers)
        if cookies is not None:
            cookie_request = httpx2.Request(active_method, active_url, headers=prepared_headers)
            cookies.set_cookie_header(cookie_request)
            prepared_headers = cookie_request.headers
        async with client.stream(
            method=active_method,
            url=active_url,
            headers=prepared_headers,
            content=active_content,
            timeout=timeout,
            follow_redirects=False,
            cookies=None,
            extensions=active_extensions,
        ) as response:
            last_request = response.request
            if cookies is not None:
                cookies.extract_cookies(response)
            next_request = response.next_request if follow_redirects else None
            if next_request is None:
                yield response
                return
            active_method = next_request.method
            active_url = next_request.url
            active_headers = resolve_headers(next_request)
            active_content = await next_request.aread()
            active_extensions = await resolve_extensions(str(next_request.url))
    if last_request is None:
        last_request = httpx2.Request(method, url)
    raise httpx2.TooManyRedirects(
        "Exceeded maximum allowed redirects.",
        request=last_request,
    )
