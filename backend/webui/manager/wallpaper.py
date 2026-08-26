"""SoAI - WebUI wallpaper upload, download, and validation service [backend/webui/manager/wallpaper.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.files.move_with_cancellation import (
    MoveFileCommittedAfterCancellationError,
    move_file_with_cancellation,
)
from core.files.operations import async_remove_if_exists, secure_filename
from core.files.temp_files import create_secure_temp_file_descriptor
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.network.http_download import download_http_stream_to_file
from core.network.outbound_http_profiles import build_default_browser_asset_headers
from core.network.urls import normalize_http_url
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.wallpaper.settings import WallpaperSettings, resolve_wallpaper_settings
from webui.manager.wallpaper_dependencies import WallpaperManagerDependencies
from webui.manager.wallpaper_download_policy import build_download_url_validator
from webui.manager.wallpaper_metadata import collect_wallpaper_metadata
from webui.manager.wallpaper_storage_files import (
    clear_wallpaper_dir,
    ensure_wallpaper_storage_path,
    prune_wallpaper_dir,
    resolve_latest_wallpaper_file,
)
from webui.manager.wallpaper_upload_validation import (
    validate_staged_image_file,
)

if TYPE_CHECKING:
    import httpx2

    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict

__all__ = ("WallpaperManager",)

LOGGER_NAME = "SoAI.webui.manager.wallpaper"


class WallpaperManager:

    def __init__(self, deps: WallpaperManagerDependencies) -> None:
        self._deps = deps
        self.config = deps.config
        self.files = deps.files
        self.runtime_flags = deps.runtime_flags
        self._token_collection = deps.token_collection
        self._cancellation_history = deps.cancellation_history
        self._cancellation_event_bus = deps.cancellation_event_bus
        self.logger = get_logger(LOGGER_NAME)

    def _resolve_settings(self) -> WallpaperSettings:
        return resolve_wallpaper_settings(self.config)

    def _resolve_storage_path(self, settings: WallpaperSettings) -> str:
        return self.files.resolve_path(settings.storage_path)

    def _resolve_temp_path(self, settings: WallpaperSettings) -> str | None:
        if settings.temp_path is None:
            return None
        return self.files.resolve_path(settings.temp_path)

    def _require_cancellation_id(self, cancellation_id: str) -> str:
        normalized_cancellation_id = normalize_cancellation_id(cancellation_id)
        if not normalized_cancellation_id:
            raise ValidationError("Wallpaper operations require a cancellation_id.")
        return normalized_cancellation_id

    async def _ensure_storage_path(self, settings: WallpaperSettings) -> str:
        return await ensure_wallpaper_storage_path(self._resolve_storage_path(settings))

    async def _resolve_wallpaper_file(self) -> tuple[str | None, os.stat_result | None]:
        settings = self._resolve_settings()
        storage_path = await self._ensure_storage_path(settings)
        return await resolve_latest_wallpaper_file(storage_path)

    async def get_current_wallpaper_info(self) -> tuple[str | None, float | None]:
        file_path, stat_result = await self._resolve_wallpaper_file()
        if not file_path or not stat_result:
            return (None, None)
        return (file_path, stat_result.st_mtime)

    async def get_current_wallpaper_details(
        self,
    ) -> tuple[str | None, float | None, JSONDict | None]:
        file_path, stat_result = await self._resolve_wallpaper_file()
        if not file_path or not stat_result:
            return (None, None, None)
        metadata = await collect_wallpaper_metadata(
            file_path=file_path,
            stat_result=stat_result,
            logger=self.logger,
        )
        return (file_path, stat_result.st_mtime, metadata)

    async def _finalize_staged_wallpaper(
        self,
        *,
        staged_file_path: str,
        extension: str,
        cancellation_token: CancellationTokenProtocol,
        settings: WallpaperSettings,
        required_bytes: int,
    ) -> None:
        cancellation_token.raise_if_cancelled()
        storage_path = await self._ensure_storage_path(settings)
        final_filepath = os.path.join(storage_path, f"wallpaper{extension}")
        try:
            if required_bytes <= 0:
                raise ValidationError("Wallpaper finalization requires a positive staged size.")
            with self._deps.storage_manager.reserve_disk_space(
                path=final_filepath,
                required_bytes=required_bytes,
                operation="webui.wallpaper.finalize",
                details={
                    "purpose": "wallpaper_storage",
                    "final_path": final_filepath,
                    "required_bytes": required_bytes,
                },
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=required_bytes):
                    await move_file_with_cancellation(
                        staged_file_path,
                        final_filepath,
                        cancellation_token,
                    )
        except MoveFileCommittedAfterCancellationError as exception:
            await async_remove_if_exists(
                exception.destination_path or final_filepath,
                logger=self.logger,
                log_level=logging.DEBUG,
            )
            raise
        await prune_wallpaper_dir(
            storage_path=storage_path,
            keep_file_path=final_filepath,
            logger=self.logger,
        )

    async def set_wallpaper_from_staged_file(
        self,
        *,
        staged_file_path: str,
        original_filename: str,
        content_type: str | None,
        declared_size_bytes: int | None,
        cancellation_token: CancellationTokenProtocol,
    ) -> None:
        settings = self._resolve_settings()
        safe_filename = secure_filename(original_filename or "")
        validated_image = await validate_staged_image_file(
            staged_file_path=staged_file_path,
            filename=safe_filename,
            content_type=content_type,
            declared_size_bytes=declared_size_bytes,
            max_size_bytes=settings.max_size_bytes,
        )
        await self._finalize_staged_wallpaper(
            staged_file_path=staged_file_path,
            extension=validated_image.extension,
            cancellation_token=cancellation_token,
            settings=settings,
            required_bytes=validated_image.size_bytes,
        )

    async def set_wallpaper_from_url(
        self,
        url: str,
        http_client: httpx2.AsyncClient,
        cancellation_id: str,
    ) -> None:
        settings = self._resolve_settings()
        normalized_url = normalize_http_url(url)
        normalized_cancellation_id = self._require_cancellation_id(cancellation_id)

        url_validator = build_download_url_validator(
            runtime_flags=self.runtime_flags,
            settings=settings,
        )
        await url_validator(normalized_url)

        staged_file_path: str | None = None
        try:
            async with cancellation_token_scope(
                self._token_collection,
                self._cancellation_history,
                self._cancellation_event_bus,
                cancellation_id=normalized_cancellation_id,
                owner="wallpaper_download",
                metadata={"url": normalized_url},
                logger=self.logger,
            ) as token:
                file_descriptor, staged_file_path = create_secure_temp_file_descriptor(
                    directory=self._resolve_temp_path(settings),
                    prefix="soai-",
                    suffix=".tmp",
                )
                os.close(file_descriptor)
                result = await download_http_stream_to_file(
                    http_client=http_client,
                    url=normalized_url,
                    destination_path=staged_file_path,
                    cancellation_token=token,
                    max_bytes=settings.max_size_bytes,
                    max_redirects=settings.download.max_redirects,
                    allow_http_scheme=True,
                    timeout_seconds=60.0,
                    request_headers=build_default_browser_asset_headers(),
                    url_validator=url_validator,
                    reservation_provider=self._deps.storage_manager,
                    reservation_path=staged_file_path,
                    reservation_operation="webui.wallpaper.download",
                    reservation_details={
                        "purpose": "wallpaper_download_temp_file",
                        "url": normalized_url,
                    },
                )
                filename_from_url = os.path.basename(result.final_url.split("?", maxsplit=1)[0])
                safe_filename = secure_filename(filename_from_url or "")
                validated_image = await validate_staged_image_file(
                    staged_file_path=staged_file_path,
                    filename=safe_filename,
                    content_type=result.content_type,
                    declared_size_bytes=result.declared_content_length,
                    max_size_bytes=settings.max_size_bytes,
                )
                await self._finalize_staged_wallpaper(
                    staged_file_path=staged_file_path,
                    extension=validated_image.extension,
                    cancellation_token=token,
                    settings=settings,
                    required_bytes=validated_image.size_bytes,
                )
                staged_file_path = None
        finally:
            if staged_file_path:
                staged_file_cleanup = async_remove_if_exists(
                    staged_file_path,
                    logger=self.logger,
                    log_level=logging.DEBUG,
                )
                await uncancel_then_cleanup(staged_file_cleanup)

    async def delete_wallpaper(self) -> None:
        settings = self._resolve_settings()
        storage_path = await self._ensure_storage_path(settings)
        await clear_wallpaper_dir(storage_path=storage_path, logger=self.logger)
