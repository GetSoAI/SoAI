"""SoAI - MCP web scraper HTTP fetching operations [backend/mcp/rag/scraper/fetching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import httpx2
from playwright.async_api import Error

from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from mcp.rag.scraper.browser_rendering import render_url_to_html
from mcp.rag.scraper.types import FetchedContent
from mcp.rag.scraper.url_processing import process_fetched_url_content
from mcp.rag.scraper.url_validation import (
    generate_url_variants,
    normalize_http_url,
)
from mcp.rag.scraper.url_variant_racing import race_url_variants

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import (
        ProgressCallbackProtocol,
        WebContentFetcherProtocol,
    )

__all__ = ("fetch_url",)


async def fetch_url(
    self: WebContentFetcherProtocol,
    url: str,
    *,
    ocr_language: str,
    progress_callback: ProgressCallbackProtocol | None = None,
) -> FetchedContent:
    normalized_url = normalize_http_url(url)
    url_variants = generate_url_variants(
        normalized_url,
        include_http_fallback_for_https=True,
    )
    if not url_variants:
        raise ValidationError(f"Failed to fetch {url}: no URL variants to try")
    rendered = None
    fetched = False
    content = b""
    content_type = ""
    final_url = normalized_url
    content_disposition: str | None = None
    https_failure: Exception | None = None
    http_variant_failure: Exception | None = None

    def _split_variants(variants: list[str]) -> tuple[list[str], list[str]]:
        https_variants: list[str] = []
        http_variants: list[str] = []
        for candidate in variants:
            scheme = (urlparse(candidate).scheme or "").lower()
            if scheme == "https":
                https_variants.append(candidate)
            elif scheme == "http":
                http_variants.append(candidate)
        return (https_variants, http_variants)

    async def _fetch_variants(variants: list[str]) -> tuple[bytes, str, str, str | None]:
        if len(variants) == 1:
            return await self.fetch_raw(
                variants[0],
                progress_callback=progress_callback,
            )
        return await race_url_variants(
            self,
            url=url,
            url_variants=variants,
            progress_callback=progress_callback,
        )

    def _resolve_render_url() -> str:
        https_variants, _http_variants = _split_variants(url_variants)
        if https_variants:
            return https_variants[0]
        parsed = urlparse(normalized_url)
        if (parsed.scheme or "").lower() in {"http", "https"} and parsed.netloc:
            return urlunparse(parsed._replace(scheme="https"))
        return normalized_url

    async def _render_via_browser(reason: str) -> None:
        nonlocal rendered
        acquired = False
        try:
            acquire_timeout_sec = max(1.0, float(self.browser_render_nav_timeout_sec))
            try:
                await asyncio.wait_for(
                    self.browser_render_semaphore.acquire(),
                    timeout=acquire_timeout_sec,
                )
            except TimeoutError as exception:
                raise ValidationError(
                    f"Browser render concurrency limit reached (max {self.browser_render_max_concurrent_pages} pages); could not start within {acquire_timeout_sec:.0f}s: {url}",
                ) from exception
            acquired = True
            async with asyncio.timeout(float(self.browser_render_nav_timeout_sec) + 15.0):
                rendered = await render_url_to_html(
                    self.runtime_flags,
                    config=self.config,
                    adblock_service=self.adblock_service,
                    url=_resolve_render_url(),
                    dns_timeout_sec=self.dns_timeout_sec,
                    headless=bool(self.browser_render_headless),
                    nav_timeout_sec=int(self.browser_render_nav_timeout_sec),
                    stabilize_ms=int(self.browser_render_stabilize_ms),
                    block_images=bool(self.browser_render_block_images),
                    block_fonts=bool(self.browser_render_block_fonts),
                    block_media=bool(self.browser_render_block_media),
                    block_ads=bool(self.browser_render_block_ads),
                    block_private_networks=True,
                )
        except TimeoutError as exception:
            raise ValidationError(
                f"{reason} browser render retry timed out after {self.browser_render_nav_timeout_sec}s: {url}",
            ) from exception
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            raise ValidationError(
                f"{reason} browser render retry failed for {url}: {type(exception).__name__}: {exception}",
            ) from exception
        except Error as exception:
            raise ValidationError(
                f"{reason} browser render retry failed for {url}: {type(exception).__name__}: {exception}",
            ) from exception
        finally:
            if acquired:
                self.browser_render_semaphore.release()

    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + float(self.fetch_variants_total_timeout_sec)
        https_variants, http_variants = _split_variants(url_variants)
        if not https_variants and not http_variants:
            raise ValidationError(f"Failed to fetch {url}: no URL variants to try")
        remaining = deadline - loop.time()
        if remaining <= 0.0:
            raise TimeoutError(f"Failed to fetch {url}: fetch timed out")
        try:
            async with asyncio.timeout(remaining):
                content, content_type, final_url, content_disposition = await _fetch_variants(
                    https_variants or http_variants,
                )
                fetched = True
        except (
            httpx2.HTTPStatusError,
            httpx2.RequestError,
            TimeoutError,
            ValidationError,
        ) as exception:
            https_failure = exception
        if not fetched and https_variants and http_variants:
            remaining = deadline - loop.time()
            if remaining <= 0.0:
                raise TimeoutError(f"Failed to fetch {url}: fetch timed out") from https_failure
            try:
                async with asyncio.timeout(remaining):
                    content, content_type, final_url, content_disposition = await _fetch_variants(
                        http_variants,
                    )
                    fetched = True
            except (
                httpx2.HTTPStatusError,
                httpx2.RequestError,
                TimeoutError,
                ValidationError,
            ) as exception:
                http_variant_failure = exception
        if not fetched:
            raise (
                https_failure or http_variant_failure or ValidationError(f"Failed to fetch {url}")
            )
    except httpx2.HTTPStatusError as exception:
        if not self.browser_render_on_http_error_enabled:
            raise
        status_code = exception.response.status_code if exception.response is not None else 0
        if status_code not in self.browser_render_on_http_error_status_codes:
            raise
        await _render_via_browser(f"HTTP {status_code}")
    except ValidationError as exception:
        if not self.browser_render_on_http_error_enabled:
            raise
        cause = exception.__cause__
        if not isinstance(cause, httpx2.HTTPStatusError):
            raise
        status_code = cause.response.status_code if cause.response is not None else 0
        if status_code not in self.browser_render_on_http_error_status_codes:
            raise
        await _render_via_browser(f"HTTP {status_code}")
    except TimeoutError:
        if not self.browser_render_on_timeout_enabled:
            raise
        await _render_via_browser("Timeout")
    if rendered is not None:
        content = rendered.html.encode("utf-8", errors="replace")
        content_type = "text/html"
        final_url = rendered.final_url
        content_disposition = None
    elif not fetched:
        raise ValidationError(f"Failed to fetch {url}: no content returned")
    return await process_fetched_url_content(
        self,
        ocr_language=ocr_language,
        content=content,
        content_type=content_type,
        final_url=final_url,
        content_disposition=content_disposition,
    )
