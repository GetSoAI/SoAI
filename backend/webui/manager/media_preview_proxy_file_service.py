"""SoAI - Remote media proxy file cache and response preparation [backend/webui/manager/media_preview_proxy_file_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.cancellation import CancellationToken
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove_if_exists
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.media_preview.media_preview_models import ProxyFile
from core.media_preview.media_preview_proxy_response import (
    build_proxy_headers,
    enforce_proxy_type_allowed,
    resolve_download_filename,
    resolve_effective_media_type,
    resolve_proxy_type,
)
from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.network.http_download import download_http_stream_to_file
from core.network.outbound_http_profiles import build_default_browser_asset_headers
from core.network.urls import normalize_http_url
from core.runtime.network_policy import OfflineModeError
from webui.manager.media_preview_proxy_cache import (
    build_cache_paths,
    build_cache_temp_path,
    build_proxy_cache_key,
    ensure_cache_dir_exists,
    promote_cache_file_with_metadata_text,
    prune_cache_dir,
    serialize_cache_metadata_text,
)
from webui.manager.media_preview_proxy_cache_entries import (
    try_prepare_cached_proxy_file,
)
from webui.manager.media_preview_proxy_cache_metadata_schema import (
    build_media_preview_cache_metadata_v1,
)
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "ProxyFileService",
    "ProxyFileServiceDependencies",
)

LOGGER_NAME = "SoAI.webui.manager.media_preview_proxy_file_service"
OPERATION = "webui.media.proxy.file"


@dataclass(frozen=True, slots=True)
class ProxyFileServiceDependencies:
    settings: MediaPreviewSettings
    policy: RemoteMediaPolicy
    cache_dir: str
    locks: AsyncLockRegistryProtocol[str]
    storage_manager: StorageManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ProxyFileServiceDependencies",
            cache_dir=self.cache_dir,
            locks=self.locks,
            policy=self.policy,
            settings=self.settings,
            storage_manager=self.storage_manager,
        )


class ProxyFileService:
    __slots__ = ("_deps",)

    def __init__(self, deps: ProxyFileServiceDependencies) -> None:
        self._deps = deps

    async def prepare_proxy_file(
        self,
        http_client: httpx2.AsyncClient,
        runtime_flags: RuntimeFlagsViewProtocol,
        source_url: str,
        *,
        download: bool,
    ) -> ProxyFile:
        logger = get_logger(LOGGER_NAME)
        normalized = normalize_http_url(source_url)
        key = build_proxy_cache_key(normalized)
        data_path, meta_path = build_cache_paths(self._deps.cache_dir, key)
        await ensure_cache_dir_exists(self._deps.cache_dir)

        async with self._deps.locks.lock(key):
            cached = await try_prepare_cached_proxy_file(
                data_path=data_path,
                meta_path=meta_path,
                download=download,
                cache_ttl_seconds=self._deps.settings.preview_client_cache_ttl_sec,
            )
            if cached is not None:
                return cached
            try:
                return await self._download_and_store(
                    http_client=http_client,
                    runtime_flags=runtime_flags,
                    normalized_url=normalized,
                    data_path=data_path,
                    meta_path=meta_path,
                    download=download,
                )
            except HTTP_RECOVERABLE_EXCEPTIONS as exception:
                if isinstance(
                    exception,
                    OfflineModeError | ValidationError | httpx2.HTTPStatusError,
                ):
                    raise
                coerced = coerce_to_soai_error(exception, operation=OPERATION)
                log_exception(
                    logger,
                    coerced,
                    message="Failed to prepare media proxy file",
                    operation=OPERATION,
                    level="warning",
                )
                raise ValidationError("Media proxy failed.") from exception

    async def _download_and_store(
        self,
        *,
        http_client: httpx2.AsyncClient,
        runtime_flags: RuntimeFlagsViewProtocol,
        normalized_url: str,
        data_path: str,
        meta_path: str,
        download: bool,
    ) -> ProxyFile:
        logger = get_logger(LOGGER_NAME)
        await self._deps.policy.enforce(runtime_flags, normalized_url, source="webui media proxy")
        temp_path = build_cache_temp_path(
            self._deps.cache_dir,
            build_proxy_cache_key(normalized_url),
        )

        async def url_validator(check_url: str) -> str | None:
            normalized_check = normalize_http_url(check_url)
            return await self._deps.policy.enforce(
                runtime_flags,
                normalized_check,
                source="webui media proxy redirect",
            )

        result = None
        try:
            result = await download_http_stream_to_file(
                http_client=http_client,
                url=normalized_url,
                destination_path=temp_path,
                cancellation_token=CancellationToken(
                    "webui_media_proxy",
                    owner="webui_media_proxy",
                    metadata={"url": normalized_url},
                ),
                max_bytes=self._deps.settings.max_fetch_size_bytes,
                max_redirects=self._deps.settings.max_redirects,
                allow_http_scheme=True,
                timeout_seconds=float(self._deps.settings.timeout_sec),
                request_headers=build_default_browser_asset_headers(),
                url_validator=url_validator,
                reservation_provider=self._deps.storage_manager,
                reservation_path=temp_path,
                reservation_operation=OPERATION,
                reservation_details={"purpose": "media_proxy_temp_file", "url": normalized_url},
            )
            final_url = normalize_http_url(result.final_url)
            upstream_content_type = str(result.content_type or "").strip() or None
            proxy_type = resolve_proxy_type(final_url=final_url, content_type=upstream_content_type)
            enforce_proxy_type_allowed(media_type=proxy_type, download=download)
            media_type = resolve_effective_media_type(
                final_url=final_url,
                content_type=upstream_content_type,
                download=download,
            )
            declared_length = (
                int(result.declared_content_length)
                if result.declared_content_length is not None
                else None
            )
            metadata_text = serialize_cache_metadata_text(
                build_media_preview_cache_metadata_v1(
                    source_url=normalized_url,
                    final_url=final_url,
                    content_type=upstream_content_type or "",
                    bytes_written=int(result.bytes_written),
                    declared_content_length=declared_length,
                ),
            )
            metadata_size = len(metadata_text.encode("utf-8"))
            with self._deps.storage_manager.reserve_many_disk_spaces(
                requests=(
                    DiskSpaceReservationRequest(
                        path=meta_path,
                        required_bytes=metadata_size,
                        operation=OPERATION,
                        details={"purpose": "media_proxy_metadata", "url": normalized_url},
                    ),
                ),
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=metadata_size):
                    await promote_cache_file_with_metadata_text(
                        temp_path=temp_path,
                        data_path=data_path,
                        meta_path=meta_path,
                        metadata_text=metadata_text,
                    )
        finally:
            temp_file_cleanup = async_remove_if_exists(
                temp_path,
                logger=logger,
                log_level=logging.DEBUG,
            )
            await uncancel_then_cleanup(temp_file_cleanup)
        await prune_cache_dir(
            self._deps.cache_dir,
            max_bytes=self._deps.settings.cache_max_size_bytes,
        )
        headers = build_proxy_headers(
            download=download,
            content_disposition_filename=resolve_download_filename(
                normalize_http_url(result.final_url) if result is not None else normalized_url,
            ),
            cache_ttl_seconds=self._deps.settings.preview_client_cache_ttl_sec,
        )
        return ProxyFile(
            status_code=200,
            media_type=media_type,
            headers=headers,
            file_path=data_path,
        )
