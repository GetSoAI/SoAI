"""SoAI - MCP web scraper HTTP fetching and retry policy [backend/mcp/rag/scraper/http_fetching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import httpx2

from core.concurrency.deadlines import deadline_after
from core.config.numeric_lenient import coerce_timeout_seconds
from core.errors.exceptions import ValidationError
from core.network.outbound_http_profiles import build_browser_document_headers
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from mcp.rag.scraper.fetch_progress import invoke_progress_callback
from mcp.rag.scraper.proxy import get_http_client
from mcp.rag.scraper.url_validation import validate_fetch_url
from mcp.rag.scraper.user_agents import get_user_agent

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import (
        ProgressCallbackProtocol,
        WebContentFetcherProtocol,
    )

__all__ = (
    "fetch_with_redirect_policy",
    "fetch_with_retries",
    "resolve_dns_timeout_seconds",
)


def backoff_delay(self: WebContentFetcherProtocol, attempt: int) -> float:
    return compute_exponential_backoff_seconds(
        attempt,
        base_seconds=float(self.fetch_retry_delay),
        maximum_seconds=60.0,
        jitter_ratio=0.1,
    )


def resolve_dns_timeout_seconds(self: WebContentFetcherProtocol) -> float:
    return coerce_timeout_seconds(self.dns_timeout_sec, default=3.0)


async def fetch_with_redirect_policy(
    self: WebContentFetcherProtocol,
    url: str,
    max_redirects: int = 10,
    *,
    source: str,
    progress_callback: ProgressCallbackProtocol | None = None,
) -> tuple[bytes, str, str, str | None]:
    current_url = url
    base_headers = build_browser_document_headers(
        user_agent=get_user_agent(self),
        accept=self.accept_header,
        accept_language=self.accept_language,
    )
    dns_timeout_sec = resolve_dns_timeout_seconds(self)
    for _redirect_index in range(max_redirects):
        current_url, pinned_ip = await validate_fetch_url(
            self.runtime_flags,
            dns_timeout_sec,
            current_url,
            source=source,
        )
        parsed = urlparse(current_url)
        original_host = parsed.hostname or ""
        async with get_http_client(
            self,
            current_url,
            pinned_ip=pinned_ip,
            original_host=original_host,
        ) as client:
            async with client.stream(
                "GET",
                current_url,
                headers=base_headers,
                timeout=self.timeout,
                follow_redirects=False,
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_url = response.headers.get("Location")
                    if not redirect_url:
                        raise ValidationError(
                            f"Redirect from {current_url} missing Location header",
                        )
                    current_url = urljoin(current_url, redirect_url)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                content_disposition = response.headers.get("content-disposition")
                content_length = response.headers.get("content-length")
                length_value: int | None = None
                if content_length:
                    try:
                        length_value = int(content_length)
                    except ValueError:
                        length_value = None
                    if length_value and length_value > self.max_size_bytes:
                        raise ValidationError(
                            f"URL content length {length_value} bytes exceeds max size of {self.max_size_bytes} bytes",
                        )
                total_size = 0
                chunk_size = (
                    int(self.stream_chunk_size)
                    if isinstance(self.stream_chunk_size, int) and self.stream_chunk_size > 0
                    else 8192
                )
                await invoke_progress_callback(progress_callback, 0, length_value, current_url)
                buffer = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    total_size += len(chunk)
                    if total_size > self.max_size_bytes:
                        raise ValidationError(
                            f"URL content exceeds max size of {self.max_size_bytes} bytes",
                        )
                    buffer.extend(chunk)
                    await invoke_progress_callback(
                        progress_callback,
                        total_size,
                        length_value,
                        current_url,
                    )
                return (
                    bytes(buffer),
                    content_type,
                    current_url,
                    content_disposition,
                )
    raise ValidationError(f"Too many redirects (>{max_redirects}) for {url}")


async def fetch_with_retries(
    self: WebContentFetcherProtocol,
    url: str,
    *,
    source: str,
    max_redirects: int = 10,
    progress_callback: ProgressCallbackProtocol | None = None,
) -> tuple[bytes, str, str, str | None]:
    last_error: Exception | None = None
    total_timeout_sec = float(self.fetch_total_timeout_sec)
    deadline = deadline_after(total_timeout_sec)

    for attempt in range(self.fetch_max_retries):
        remaining = deadline.remaining_seconds()
        if remaining <= 0.0:
            raise TimeoutError(f"Fetch timed out after {self.fetch_total_timeout_sec}s: {url}")
        try:
            return await asyncio.wait_for(
                fetch_with_redirect_policy(
                    self,
                    url,
                    max_redirects=max_redirects,
                    source=source,
                    progress_callback=progress_callback,
                ),
                timeout=remaining,
            )
        except TimeoutError as exception:
            raise TimeoutError(
                f"Fetch timed out after {self.fetch_total_timeout_sec}s: {url}",
            ) from exception
        except httpx2.HTTPStatusError as exception:
            status = exception.response.status_code
            if status >= 500 or status == 429:
                last_error = exception
            else:
                raise
        except (httpx2.RequestError, OSError) as exception:
            last_error = exception
        if attempt < self.fetch_max_retries - 1 and last_error is not None:
            remaining = deadline.remaining_seconds()
            if remaining <= 0.0:
                raise TimeoutError(f"Fetch timed out after {self.fetch_total_timeout_sec}s: {url}")
            delay = backoff_delay(self, attempt)
            sleep_duration = min(delay, max(0.0, remaining))
            try:
                await asyncio.wait_for(asyncio.sleep(sleep_duration), timeout=remaining)
            except TimeoutError as exception:
                raise TimeoutError(
                    f"Fetch timed out after {self.fetch_total_timeout_sec}s: {url}",
                ) from exception
    if last_error is not None:
        raise ValidationError(
            f"Failed to fetch {url}: {type(last_error).__name__}: {last_error}",
        ) from last_error
    raise ValidationError(f"Failed to fetch {url}")
