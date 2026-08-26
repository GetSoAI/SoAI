"""SoAI - Page screenshot preview service [backend/webui/manager/media_preview_page_screenshot_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.media_preview.media_preview_models import ProxyFile
from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.network.urls import normalize_http_url
from core.webui_manager.protocols import (
    WebUILinkPreviewScreenshotCapturerProtocol,
    WebUIPageScreenshotServiceProtocol,
)
from webui.manager.media_preview_proxy_cache import (
    build_cache_paths,
    build_cache_temp_path,
    build_proxy_cache_key,
    ensure_cache_dir_exists,
    promote_cache_file_with_metadata_text,
    prune_cache_dir,
    remove_temp_file_if_present,
    serialize_cache_metadata_text,
)
from webui.manager.media_preview_proxy_cache_entries import (
    try_prepare_cached_page_screenshot_png,
)
from webui.manager.media_preview_proxy_cache_metadata_schema import (
    build_media_preview_cache_metadata_v1,
)
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "PageScreenshotService",
    "PageScreenshotServiceDependencies",
)

LOGGER_NAME = "SoAI.webui.manager.media_preview_page_screenshot_service"
OPERATION_STORE = "webui.media.page_screenshot.store"


def _enforce_screenshot_size(settings: MediaPreviewSettings, image_size: int) -> None:
    max_size = min(int(settings.max_fetch_size_bytes), int(settings.cache_max_size_bytes))
    if image_size > max_size:
        raise ValidationError(f"Page screenshot exceeds the configured limit of {max_size} bytes.")


def _build_cache_key_text(page_url: str) -> str:
    normalized = str(page_url or "").strip()
    if not normalized:
        raise ValidationError("Page screenshot URL must be provided.")
    return f"{normalized}#soai_webui_page_screenshot"


@dataclass(frozen=True, slots=True)
class PageScreenshotServiceDependencies:
    settings: MediaPreviewSettings
    policy: RemoteMediaPolicy
    cache_dir: str
    locks: AsyncLockRegistryProtocol[str]
    screenshot_capturer: WebUILinkPreviewScreenshotCapturerProtocol
    storage_manager: StorageManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PageScreenshotServiceDependencies",
            cache_dir=self.cache_dir,
            locks=self.locks,
            policy=self.policy,
            screenshot_capturer=self.screenshot_capturer,
            settings=self.settings,
            storage_manager=self.storage_manager,
        )


class PageScreenshotService(WebUIPageScreenshotServiceProtocol):
    __slots__ = ("_deps",)

    def __init__(self, deps: PageScreenshotServiceDependencies) -> None:
        self._deps = deps

    @override
    async def store_page_screenshot_png(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
        *,
        url: str,
        image_bytes_png: bytes,
    ) -> None:
        normalized_url = normalize_http_url(url)
        if not isinstance(image_bytes_png, bytes | bytearray) or not image_bytes_png:
            raise ValidationError("Page screenshot bytes must be provided.")
        image_data = bytes(image_bytes_png)
        _enforce_screenshot_size(self._deps.settings, len(image_data))
        await self._deps.policy.enforce(
            runtime_flags,
            normalized_url,
            source="webui media page_screenshot",
        )
        cache_key_text = _build_cache_key_text(normalized_url)
        key = build_proxy_cache_key(cache_key_text)
        data_path, meta_path = build_cache_paths(self._deps.cache_dir, key)
        await ensure_cache_dir_exists(self._deps.cache_dir)

        async with self._deps.locks.lock(key):
            cached = await try_prepare_cached_page_screenshot_png(
                data_path=data_path,
                meta_path=meta_path,
                cache_ttl_seconds=self._deps.settings.preview_client_cache_ttl_sec,
            )
            if cached is not None:
                return
            await self._store_page_screenshot_png_locked(
                normalized_url=normalized_url,
                key=key,
                data_path=data_path,
                meta_path=meta_path,
                image_bytes_png=image_data,
            )

        await prune_cache_dir(
            self._deps.cache_dir,
            max_bytes=self._deps.settings.cache_max_size_bytes,
        )

    @override
    async def prepare_page_screenshot_file(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
    ) -> ProxyFile:
        normalized_url = normalize_http_url(source_url)
        await self._deps.policy.enforce(
            runtime_flags,
            normalized_url,
            source="webui media page_screenshot",
        )
        cache_key_text = _build_cache_key_text(normalized_url)
        key = build_proxy_cache_key(cache_key_text)
        data_path, meta_path = build_cache_paths(self._deps.cache_dir, key)
        await ensure_cache_dir_exists(self._deps.cache_dir)

        async with self._deps.locks.lock(key):
            cached = await try_prepare_cached_page_screenshot_png(
                data_path=data_path,
                meta_path=meta_path,
                cache_ttl_seconds=self._deps.settings.preview_client_cache_ttl_sec,
            )
            if cached is not None:
                return cached
            screenshot_bytes, screenshot_error = (
                await self._deps.screenshot_capturer.capture_link_preview_screenshot_png(
                    runtime_flags,
                    url=normalized_url,
                    source_html=None,
                )
            )
            if screenshot_bytes is None:
                message = (
                    screenshot_error.strip()
                    if isinstance(screenshot_error, str) and screenshot_error.strip()
                    else "Page screenshot capture failed."
                )
                raise ValidationError(message)
            _enforce_screenshot_size(self._deps.settings, len(screenshot_bytes))
            await self._store_page_screenshot_png_locked(
                normalized_url=normalized_url,
                key=key,
                data_path=data_path,
                meta_path=meta_path,
                image_bytes_png=screenshot_bytes,
            )

            cached = await try_prepare_cached_page_screenshot_png(
                data_path=data_path,
                meta_path=meta_path,
                cache_ttl_seconds=self._deps.settings.preview_client_cache_ttl_sec,
            )
            if cached is not None:
                return cached
            raise ValidationError("Page screenshot cache entry was not created.")

    async def _store_page_screenshot_png_locked(
        self,
        *,
        normalized_url: str,
        key: str,
        data_path: str,
        meta_path: str,
        image_bytes_png: bytes,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        temp_path = build_cache_temp_path(self._deps.cache_dir, key)
        try:
            image_size = len(image_bytes_png)
            metadata_text = serialize_cache_metadata_text(
                build_media_preview_cache_metadata_v1(
                    source_url=normalized_url,
                    final_url=normalized_url,
                    content_type="image/png",
                    bytes_written=image_size,
                    declared_content_length=image_size,
                ),
            )
            metadata_size = len(metadata_text.encode("utf-8"))
            with self._deps.storage_manager.reserve_many_disk_spaces(
                requests=(
                    DiskSpaceReservationRequest(
                        path=temp_path,
                        required_bytes=image_size,
                        operation=OPERATION_STORE,
                        details={
                            "purpose": "page_screenshot_cache_data",
                            "url": normalized_url,
                        },
                    ),
                    DiskSpaceReservationRequest(
                        path=meta_path,
                        required_bytes=metadata_size,
                        operation=OPERATION_STORE,
                        details={
                            "purpose": "page_screenshot_cache_metadata",
                            "url": normalized_url,
                        },
                    ),
                ),
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=image_size):
                    await asyncio.to_thread(_write_binary_file, temp_path, image_bytes_png)
                with claim_reserved_write(reservation, size_bytes=metadata_size):
                    await promote_cache_file_with_metadata_text(
                        temp_path=temp_path,
                        data_path=data_path,
                        meta_path=meta_path,
                        metadata_text=metadata_text,
                    )
        except RECOVERABLE_EXCEPTIONS as exception:
            error = coerce_to_soai_error(exception, operation=OPERATION_STORE)
            log_exception(
                logger,
                error,
                message="Failed to store page screenshot preview",
                operation=OPERATION_STORE,
                details={"url": normalized_url},
                level="warning",
            )
            raise ValidationError("Page screenshot store failed.") from exception
        finally:
            await remove_temp_file_if_present(
                logger=logger,
                operation=OPERATION_STORE,
                temp_path=temp_path,
                message="Failed to remove temporary page screenshot file (non-critical).",
            )


def _write_binary_file(path: str, data: bytes) -> None:
    with open_binary(path, mode="wb") as handle:
        handle.write(data)
        flush_and_fsync_file(handle)
