"""SoAI - Link preview resolution service [backend/webui/manager/media_preview_link_preview_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx2
from bs4 import BeautifulSoup

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.files.content_types import resolve_content_type_charset
from core.logging.trace import get_logger
from core.media_preview.media_preview_classification import (
    classify_content_type_for_link_preview,
    classify_url_by_extension,
    try_parse_youtube_embed,
)
from core.media_preview.media_preview_models import MediaLinkPreview
from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.network.urls import normalize_http_url
from core.runtime.network_policy import OfflineModeError
from core.web.html_metadata import extract_html_title, extract_page_metadata
from core.webui_manager.protocols import WebUIPageScreenshotServiceProtocol
from webui.manager.media_preview_fetcher import BoundedMediaFetcher
from webui.manager.media_preview_link_preview_output import (
    build_blocked_link_preview,
    build_direct_media_link_preview,
    build_download_link_preview,
    build_page_link_preview,
    build_page_screenshot_preview_url,
    build_proxy_preview_url,
    build_text_link_preview,
)
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy
from webui.manager.media_preview_youtube_embed_preview import (
    build_youtube_embed_link_preview,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.webui_manager.protocols import WebUILinkPreviewScreenshotCapturerProtocol

__all__ = (
    "LinkPreviewService",
    "LinkPreviewServiceDependencies",
)

LOGGER_NAME = "SoAI.webui.manager.media_preview_link_preview_service"
OPERATION_LINK_PREVIEW_THUMBNAIL_ENFORCE = "webui.media.link_preview.thumbnail.enforce"
OPERATION_LINK_PREVIEW_SCREENSHOT_STORE = "webui.media.link_preview.screenshot.store"


@dataclass(frozen=True, slots=True)
class LinkPreviewServiceDependencies:
    settings: MediaPreviewSettings
    policy: RemoteMediaPolicy
    fetcher: BoundedMediaFetcher
    page_screenshots: WebUIPageScreenshotServiceProtocol
    screenshot_capturer: WebUILinkPreviewScreenshotCapturerProtocol
    locks: AsyncLockRegistryProtocol[str]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LinkPreviewServiceDependencies",
            fetcher=self.fetcher,
            locks=self.locks,
            policy=self.policy,
            page_screenshots=self.page_screenshots,
            screenshot_capturer=self.screenshot_capturer,
            settings=self.settings,
        )


class LinkPreviewService:
    __slots__ = ("_cache", "_deps")

    def __init__(self, deps: LinkPreviewServiceDependencies) -> None:
        self._deps = deps
        self._cache: TTLCache[str, MediaLinkPreview] = TTLCache(
            TTLCacheDependencies(ttl_seconds=300.0, max_size=2048),
        )

    async def get_link_preview(
        self,
        http_client: httpx2.AsyncClient,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
    ) -> MediaLinkPreview:
        logger = get_logger(LOGGER_NAME)
        normalized = normalize_http_url(source_url)
        cached = self._cache.get(normalized)
        if cached is not None:
            return cached
        async with self._deps.locks.lock(normalized):
            cached = self._cache.get(normalized)
            if cached is not None:
                return cached
            await self._deps.policy.enforce(
                runtime_flags,
                normalized,
                source="webui media link_preview",
            )

            youtube = try_parse_youtube_embed(normalized)
            if youtube is not None:
                embed_url, thumb_url = youtube
                preview = await build_youtube_embed_link_preview(
                    http_client=http_client,
                    settings=self._deps.settings,
                    fetcher=self._deps.fetcher,
                    policy=self._deps.policy,
                    runtime_flags=runtime_flags,
                    source_url=normalized,
                    embed_url=embed_url,
                    thumb_url=thumb_url,
                    logger=logger,
                )
                self._cache.put(normalized, preview)
                return preview

            media_type, _mime = classify_url_by_extension(normalized)
            if media_type in {"image", "audio", "video"}:
                preview = build_direct_media_link_preview(
                    media_type=media_type,
                    source_url=normalized,
                    final_url=normalized,
                )
                self._cache.put(normalized, preview)
                return preview

            if media_type == "document":
                preview = build_download_link_preview(
                    media_type="document",
                    source_url=normalized,
                    final_url=normalized,
                )
                self._cache.put(normalized, preview)
                return preview

            if media_type == "text":
                preview = build_text_link_preview(source_url=normalized, final_url=normalized)
                self._cache.put(normalized, preview)
                return preview

            fetch_result = await self._deps.fetcher.fetch_bytes_bounded(
                http_client,
                normalized,
                runtime_flags,
                max_bytes=min(self._deps.settings.max_fetch_size_bytes, 256 * 1024),
                timeout=self._deps.settings.timeout_sec,
                headers={"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"},
                source="webui media link_preview html",
            )
            final_url = fetch_result.final_url
            content_type = fetch_result.content_type
            payload_bytes = fetch_result.payload_bytes
            if fetch_result.blocked_response is not None:
                preview = build_blocked_link_preview(source_url=normalized)
                self._cache.put(normalized, preview)
                return preview
            type_by_content_type = classify_content_type_for_link_preview(content_type)
            if type_by_content_type is not None:
                if type_by_content_type in {"image", "audio", "video"}:
                    preview = build_direct_media_link_preview(
                        media_type=type_by_content_type,
                        source_url=normalized,
                        final_url=final_url,
                    )
                    self._cache.put(normalized, preview)
                    return preview
                if type_by_content_type == "text":
                    preview = build_text_link_preview(source_url=normalized, final_url=final_url)
                    self._cache.put(normalized, preview)
                    return preview
                if type_by_content_type in {"document", "file"}:
                    preview = build_download_link_preview(
                        media_type=type_by_content_type,
                        source_url=normalized,
                        final_url=final_url,
                    )
                    self._cache.put(normalized, preview)
                    return preview
            decoded = payload_bytes.decode(
                resolve_content_type_charset(content_type),
                errors="replace",
            )
            soup = BeautifulSoup(decoded, "html.parser")
            base_url = final_url
            title_text = extract_html_title(soup, base_url)
            metadata = extract_page_metadata(soup)
            thumbnail = metadata.thumbnail_url.strip() if metadata.thumbnail_url else ""
            page_thumbnail_proxy: str | None = None
            if thumbnail:
                try:
                    absolute_thumb = normalize_http_url(urljoin(base_url, thumbnail))
                except ValidationError as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Link preview thumbnail URL was invalid; falling back to screenshot.",
                        operation=OPERATION_LINK_PREVIEW_THUMBNAIL_ENFORCE,
                        details={"thumbnail_url": thumbnail},
                        level="debug",
                    )
                    absolute_thumb = ""
                if absolute_thumb:
                    try:
                        await self._deps.policy.enforce(
                            runtime_flags,
                            absolute_thumb,
                            source="webui media link_preview thumbnail",
                        )
                        page_thumbnail_proxy = build_proxy_preview_url(
                            absolute_thumb,
                            download=False,
                        )
                    except (OfflineModeError, ValidationError) as exception:
                        log_handled_exception(
                            logger,
                            exception,
                            message="Link preview thumbnail was blocked; falling back to screenshot.",
                            operation=OPERATION_LINK_PREVIEW_THUMBNAIL_ENFORCE,
                            details={"thumbnail_url": absolute_thumb},
                            level="debug",
                        )
                        page_thumbnail_proxy = None

            if page_thumbnail_proxy is None:
                screenshot_bytes, _screenshot_error = (
                    await self._deps.screenshot_capturer.capture_link_preview_screenshot_png(
                        runtime_flags,
                        url=final_url,
                        source_html=decoded,
                    )
                )
                if screenshot_bytes is not None:
                    try:
                        await self._deps.page_screenshots.store_page_screenshot_png(
                            runtime_flags,
                            url=final_url,
                            image_bytes_png=screenshot_bytes,
                        )
                        page_thumbnail_proxy = build_page_screenshot_preview_url(final_url)
                    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
                        error = coerce_to_soai_error(
                            exception,
                            operation=OPERATION_LINK_PREVIEW_SCREENSHOT_STORE,
                        )
                        log_exception(
                            logger,
                            error,
                            message="Failed to store link preview screenshot (non-fatal).",
                            operation=OPERATION_LINK_PREVIEW_SCREENSHOT_STORE,
                            details={"url": final_url},
                            level="warning",
                        )

            description = metadata.description.strip() if metadata.description else ""
            preview = build_page_link_preview(
                source_url=normalized,
                final_url=final_url,
                title=title_text.strip() if title_text.strip() else None,
                description=description or None,
                thumbnail_url=page_thumbnail_proxy,
            )
            self._cache.put(normalized, preview)
            return preview
