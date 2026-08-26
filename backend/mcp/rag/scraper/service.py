"""SoAI - MCP web scraper service [backend/mcp/rag/scraper/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes
from core.config.numeric_lenient import coerce_lenient_bounded_float
from core.errors.exceptions import ValidationError
from core.files.protocols import FileParserProtocol
from core.network.urls import normalize_http_url
from core.validation.integers import is_strict_int
from mcp.rag.scraper.dependencies import WebContentFetcherDependencies
from mcp.rag.scraper.http_fetching import fetch_with_retries
from mcp.rag.scraper.user_agents import DEFAULT_USER_AGENTS

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol, ConfigValue
    from mcp.rag.scraper.internal_protocols import ProgressCallbackProtocol

__all__ = ("WebContentFetcher",)


def _is_valid_sequential_index(index: int) -> bool:
    return isinstance(index, int) and index >= 0


class WebContentFetcher:
    def __init__(self, deps: WebContentFetcherDependencies) -> None:
        if not isinstance(deps, WebContentFetcherDependencies):
            raise ValidationError("WebContentFetcherDependencies are required.")
        self.http_client = deps.http_client
        self.runtime_flags = deps.runtime_flags
        self.storage_manager = deps.storage_manager
        self.adblock_service = deps.adblock_service
        config = deps.config
        self.config: ConfigProtocol = config
        self.timeout = max(1, int(config.get_int("TOOLS.RAG.WEB.REQUEST_TIMEOUT")))
        self.fetch_total_timeout_sec = max(
            1,
            int(config.get_int("TOOLS.RAG.WEB.FETCH_TOTAL_TIMEOUT_SEC")),
        )
        self.fetch_variants_total_timeout_sec = max(
            1,
            int(config.get_int("TOOLS.RAG.WEB.FETCH_VARIANTS_TOTAL_TIMEOUT_SEC")),
        )
        self.max_size_bytes = max(
            1024,
            mib_to_bytes(config.get_int("TOOLS.RAG.WEB.MAX_URL_SIZE_MB")),
        )
        self.dns_timeout_sec = coerce_lenient_bounded_float(
            config.get("TOOLS.RAG.WEB.DNS_TIMEOUT_SEC"),
            default=5.0,
            minimum=0.5,
            maximum=30.0,
        )
        self.static_user_agent = config.require_str("TOOLS.RAG.WEB.USER_AGENT")
        self.accept_language = config.require_str("TOOLS.RAG.WEB.ACCEPT_LANGUAGE")
        self.accept_header = config.require_str("TOOLS.RAG.WEB.ACCEPT_HEADER")
        self.fetch_max_retries = min(
            10,
            max(1, int(config.get_int("TOOLS.RAG.WEB.FETCH_RETRY_ATTEMPTS"))),
        )
        self.fetch_retry_delay = max(0, int(config.get_int("TOOLS.RAG.WEB.FETCH_RETRY_DELAY")))
        self.stream_chunk_size = max(1024, int(config.get_int("TOOLS.RAG.WEB.STREAM_CHUNK_SIZE")))
        self.html_parse_timeout = max(5, int(config.get_int("TOOLS.RAG.WEB.HTML_PARSE_TIMEOUT")))
        self.document_parse_timeout = max(5, int(config.get_int("TOOLS.RAG.WEB.PDF_PARSE_TIMEOUT")))
        self.strip_link_urls = config.get_bool("TOOLS.RAG.WEB.MARKDOWN.STRIP_LINK_URLS")
        self.strip_images = config.get_bool("TOOLS.RAG.WEB.MARKDOWN.STRIP_IMAGES")
        self.ua_rotation_enabled = config.get_bool("TOOLS.RAG.WEB.USER_AGENT_ROTATION.ENABLED")
        self.ua_rotation_mode = config.require_str("TOOLS.RAG.WEB.USER_AGENT_ROTATION.MODE")
        custom_agents = config.get("TOOLS.RAG.WEB.USER_AGENT_ROTATION.CUSTOM_AGENTS")
        parsed_custom_agents: list[str] = []
        if isinstance(custom_agents, list | tuple):
            for agent in custom_agents:
                if not isinstance(agent, str):
                    continue
                stripped = agent.strip()
                if stripped:
                    parsed_custom_agents.append(stripped)
        self.ua_agents = parsed_custom_agents or list(DEFAULT_USER_AGENTS)
        self.ua_sequential_index: int = 0
        self.proxy_enabled = config.get_bool("TOOLS.RAG.WEB.PROXY.ENABLED")
        self.proxy_http = config.require_str_value("TOOLS.RAG.WEB.PROXY.HTTP_PROXY")
        self.proxy_https = config.require_str_value("TOOLS.RAG.WEB.PROXY.HTTPS_PROXY")
        self.proxy_socks5 = config.require_str_value("TOOLS.RAG.WEB.PROXY.SOCKS5_PROXY")
        self.proxy_no_proxy = config.require_str("TOOLS.RAG.WEB.PROXY.NO_PROXY")
        self.proxy_rotation_enabled = config.get_bool("TOOLS.RAG.WEB.PROXY.ROTATION_ENABLED")
        proxy_list = config.get("TOOLS.RAG.WEB.PROXY.PROXY_LIST")
        parsed_proxy_list: list[str] = []
        if isinstance(proxy_list, list | tuple):
            for proxy in proxy_list:
                if not isinstance(proxy, str):
                    continue
                stripped_proxy = proxy.strip()
                if stripped_proxy:
                    parsed_proxy_list.append(stripped_proxy)
        self.proxy_list = parsed_proxy_list
        self.proxy_sequential_index: int = 0
        self.browser_render_on_timeout_enabled = config.get_bool(
            "TOOLS.RAG.WEB.BROWSER_RENDER_ON_TIMEOUT_ENABLED",
        )
        self.browser_render_on_http_error_enabled = config.get_bool(
            "TOOLS.RAG.WEB.BROWSER_RENDER_ON_HTTP_ERROR_ENABLED",
        )
        self.browser_render_on_http_error_status_codes = self._resolve_http_error_status_codes(
            config.get("TOOLS.RAG.WEB.BROWSER_RENDER_ON_HTTP_ERROR_STATUS_CODES"),
        )
        self.browser_render_headless = config.get_bool("TOOLS.RAG.WEB.BROWSER_RENDER_HEADLESS")
        self.browser_render_nav_timeout_sec = max(
            1,
            int(config.get_int("TOOLS.RAG.WEB.BROWSER_RENDER_NAV_TIMEOUT_SEC")),
        )
        self.browser_render_stabilize_ms = max(
            0,
            int(config.get_int("TOOLS.RAG.WEB.BROWSER_RENDER_STABILIZE_MS")),
        )
        self.browser_render_max_concurrent_pages = max(
            1,
            int(config.get_int("TOOLS.RAG.WEB.BROWSER_RENDER_MAX_CONCURRENT_PAGES")),
        )
        self.browser_render_semaphore = asyncio.Semaphore(self.browser_render_max_concurrent_pages)
        self.browser_render_block_images = config.get_bool(
            "TOOLS.RAG.WEB.BROWSER_RENDER_BLOCK_IMAGES",
        )
        self.browser_render_block_fonts = config.get_bool(
            "TOOLS.RAG.WEB.BROWSER_RENDER_BLOCK_FONTS",
        )
        self.browser_render_block_media = config.get_bool(
            "TOOLS.RAG.WEB.BROWSER_RENDER_BLOCK_MEDIA",
        )
        self.browser_render_block_ads = config.get_bool("TOOLS.RAG.WEB.BROWSER_RENDER_BLOCK_ADS")
        self.charset_detector = deps.charset_detector
        self.magic_detector = deps.magic_detector
        self.html_parser = deps.html_parser
        self.parsers: dict[str, FileParserProtocol] = deps.parser_registry

    def _resolve_http_error_status_codes(self, value: ConfigValue | None) -> frozenset[int]:
        if value is None:
            return frozenset()
        if not isinstance(value, list | tuple | set | frozenset):
            return frozenset()
        codes: list[int] = []
        for item in value:
            if not is_strict_int(item):
                continue
            if 100 <= item <= 599:
                codes.append(item)
        return frozenset(codes)

    def set_ua_sequential_index(self, index: int) -> None:
        if _is_valid_sequential_index(index):
            self.ua_sequential_index = index

    def set_proxy_sequential_index(self, index: int) -> None:
        if _is_valid_sequential_index(index):
            self.proxy_sequential_index = index

    async def fetch_raw(
        self,
        url: str,
        *,
        offline_source: str | None = None,
        max_redirects: int = 10,
        progress_callback: ProgressCallbackProtocol | None = None,
    ) -> tuple[bytes, str, str, str | None]:
        source = offline_source or "URL content fetch"
        return await fetch_with_retries(
            self,
            normalize_http_url(url),
            max_redirects=max_redirects,
            source=source,
            progress_callback=progress_callback,
        )
