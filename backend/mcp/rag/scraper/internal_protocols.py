"""SoAI - MCP RAG scraper internal protocols [backend/mcp/rag/scraper/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, override

import httpx2
from charset_normalizer.models import CharsetMatches

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.config.protocols import ConfigProtocol
from core.files.protocols import FileParserProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.mcp.protocols_main import MCPWebFetcherProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol

if TYPE_CHECKING:
    type CharsetDetectionResultProtocol = CharsetMatches
    type ProgressCallbackProtocol = Callable[[int, int | None, str], None | Awaitable[None]]

__all__ = (
    "CharsetDetectorProtocol",
    "MagicDetectorProtocol",
    "WebContentFetcherProtocol",
)


class CharsetDetectorProtocol(Protocol):
    def __call__(
        self,
        _sequences: bytes | bytearray,
        /,
    ) -> CharsetDetectionResultProtocol: ...


class MagicDetectorProtocol(Protocol):
    def from_buffer(self, buf: bytes) -> str: ...


class WebContentFetcherProtocol(MCPWebFetcherProtocol, Protocol):
    http_client: httpx2.AsyncClient
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    storage_manager: StorageManagerProtocol
    adblock_service: EasyListAdblockServiceProtocol | None
    timeout: int
    fetch_total_timeout_sec: int
    fetch_variants_total_timeout_sec: int
    max_size_bytes: int
    dns_timeout_sec: float
    accept_language: str
    accept_header: str
    fetch_max_retries: int
    fetch_retry_delay: int
    stream_chunk_size: int
    html_parse_timeout: int
    document_parse_timeout: int
    strip_link_urls: bool
    strip_images: bool
    parsers: dict[str, FileParserProtocol]
    charset_detector: CharsetDetectorProtocol
    magic_detector: MagicDetectorProtocol
    html_parser: str
    static_user_agent: str
    ua_rotation_enabled: bool
    ua_rotation_mode: str
    ua_agents: list[str]
    ua_sequential_index: int
    proxy_enabled: bool
    proxy_http: str
    proxy_https: str
    proxy_socks5: str
    proxy_no_proxy: str
    proxy_rotation_enabled: bool
    proxy_list: list[str]
    proxy_sequential_index: int
    browser_render_on_timeout_enabled: bool
    browser_render_on_http_error_enabled: bool
    browser_render_on_http_error_status_codes: frozenset[int]
    browser_render_headless: bool
    browser_render_nav_timeout_sec: int
    browser_render_stabilize_ms: int
    browser_render_max_concurrent_pages: int
    browser_render_block_images: bool
    browser_render_block_fonts: bool
    browser_render_block_media: bool
    browser_render_block_ads: bool
    browser_render_semaphore: asyncio.Semaphore

    def set_ua_sequential_index(self, index: int) -> None: ...

    def set_proxy_sequential_index(self, index: int) -> None: ...

    @override
    async def fetch_raw(
        self,
        url: str,
        *,
        offline_source: str | None = None,
        max_redirects: int = 10,
        progress_callback: ProgressCallbackProtocol | None = None,
    ) -> tuple[bytes, str, str, str | None]: ...
