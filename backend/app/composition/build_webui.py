"""SoAI - WebUI manager composition for application assembly [backend/app/composition/build_webui.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.webui.link_preview_screenshot_capturer import (
    LinkPreviewScreenshotCapturer,
    LinkPreviewScreenshotCapturerDependencies,
)
from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.media_preview.media_preview_settings import resolve_media_preview_settings
from core.network.dns_cache import DnsResolutionCache
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TokenCollectionProtocol,
)
from core.webui_manager.protocols import WebUIManagerDatabaseDependencies
from webui.manager.dependencies import WebUIManagerDependencies
from webui.manager.guards import build_auth_guards
from webui.manager.media_preview_fetcher import BoundedMediaFetcher
from webui.manager.media_preview_link_preview_service import (
    LinkPreviewService,
    LinkPreviewServiceDependencies,
)
from webui.manager.media_preview_page_screenshot_service import (
    PageScreenshotService,
    PageScreenshotServiceDependencies,
)
from webui.manager.media_preview_proxy_file_service import (
    ProxyFileService,
    ProxyFileServiceDependencies,
)
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy
from webui.manager.media_preview_text_preview_service import (
    TextPreviewService,
    TextPreviewServiceDependencies,
)
from webui.manager.service import WebUIManager
from webui.manager.wallpaper import WallpaperManager
from webui.manager.wallpaper_dependencies import WallpaperManagerDependencies

__all__ = ("build_webui_manager",)


def build_webui_manager(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    database_core: DatabaseCoreProtocol,
    database: WebUIManagerDatabaseDependencies,
    storage_manager: StorageManagerProtocol,
) -> WebUIManager:
    wallpaper_manager = WallpaperManager(
        WallpaperManagerDependencies(
            config=config,
            files=files,
            runtime_flags=runtime_flags,
            storage_manager=storage_manager,
            token_collection=token_collection,
            cancellation_history=cancellation_history,
            cancellation_event_bus=cancellation_event_bus,
        ),
    )
    auth_guard_bundle = build_auth_guards(config, database_core)
    media_preview_settings = resolve_media_preview_settings(config)
    dns_cache = DnsResolutionCache(ttl_seconds=60.0, max_entries=1024)
    media_policy = RemoteMediaPolicy(media_preview_settings, dns_cache)
    media_fetcher = BoundedMediaFetcher(media_preview_settings, media_policy)
    proxy_locks: AsyncLockRegistryProtocol[str] = TTLAsyncLockRegistry(
        TTLAsyncLockRegistryDependencies(ttl_seconds=3600.0, max_size=10000),
    )
    proxy_file_service = ProxyFileService(
        ProxyFileServiceDependencies(
            settings=media_preview_settings,
            policy=media_policy,
            cache_dir=files.resolve_path(media_preview_settings.cache_storage_path),
            locks=proxy_locks,
            storage_manager=storage_manager,
        ),
    )
    link_preview_locks: AsyncLockRegistryProtocol[str] = TTLAsyncLockRegistry(
        TTLAsyncLockRegistryDependencies(ttl_seconds=300.0, max_size=4096),
    )
    page_screenshot_locks: AsyncLockRegistryProtocol[str] = TTLAsyncLockRegistry(
        TTLAsyncLockRegistryDependencies(ttl_seconds=3600.0, max_size=4096),
    )
    screenshot_capturer = LinkPreviewScreenshotCapturer(
        LinkPreviewScreenshotCapturerDependencies(
            config=config,
            settings=media_preview_settings,
            policy=media_policy,
        ),
    )
    page_screenshot_service = PageScreenshotService(
        PageScreenshotServiceDependencies(
            settings=media_preview_settings,
            policy=media_policy,
            cache_dir=files.resolve_path(media_preview_settings.cache_storage_path),
            locks=page_screenshot_locks,
            screenshot_capturer=screenshot_capturer,
            storage_manager=storage_manager,
        ),
    )
    link_preview_service = LinkPreviewService(
        LinkPreviewServiceDependencies(
            settings=media_preview_settings,
            policy=media_policy,
            fetcher=media_fetcher,
            screenshot_capturer=screenshot_capturer,
            page_screenshots=page_screenshot_service,
            locks=link_preview_locks,
        ),
    )
    text_preview_service = TextPreviewService(
        TextPreviewServiceDependencies(
            settings=media_preview_settings,
            policy=media_policy,
            fetcher=media_fetcher,
        ),
    )
    return WebUIManager(
        WebUIManagerDependencies(
            database=database,
            config=config,
            files=files,
            link_previews=link_preview_service,
            text_previews=text_preview_service,
            proxy_files=proxy_file_service,
            page_screenshots=page_screenshot_service,
            wallpaper_manager=wallpaper_manager,
            auth_guards=auth_guard_bundle,
        ),
    )
