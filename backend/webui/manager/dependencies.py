"""SoAI - WebUIManager dependencies dataclass [backend/webui/manager/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.files.protocols import FilesPathResolverProtocol
from core.wallpaper.protocols import WallpaperManagerProtocol
from core.webui_manager.protocols import (
    WebUILinkPreviewServiceProtocol,
    WebUIManagerDatabaseDependencies,
    WebUIPageScreenshotServiceProtocol,
    WebUIProxyFileServiceProtocol,
    WebUITextPreviewServiceProtocol,
)

if TYPE_CHECKING:
    from webui.manager.guards import AuthGuardBundle

__all__ = ("WebUIManagerDependencies",)


@dataclass(frozen=True, slots=True)
class WebUIManagerDependencies:
    database: WebUIManagerDatabaseDependencies
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    link_previews: WebUILinkPreviewServiceProtocol
    text_previews: WebUITextPreviewServiceProtocol
    proxy_files: WebUIProxyFileServiceProtocol
    page_screenshots: WebUIPageScreenshotServiceProtocol
    wallpaper_manager: WallpaperManagerProtocol
    auth_guards: AuthGuardBundle

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WebUIManagerDependencies",
            auth_guards=self.auth_guards,
            config=self.config,
            database=self.database,
            files=self.files,
            link_previews=self.link_previews,
            page_screenshots=self.page_screenshots,
            proxy_files=self.proxy_files,
            text_previews=self.text_previews,
            wallpaper_manager=self.wallpaper_manager,
        )
