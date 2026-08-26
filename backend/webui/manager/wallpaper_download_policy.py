"""SoAI - Wallpaper download URL policy [backend/webui/manager/wallpaper_download_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.wallpaper.settings import WallpaperSettings
from webui.manager.remote_asset_policy import build_remote_asset_url_validator

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("build_download_url_validator",)


def build_download_url_validator(
    *,
    runtime_flags: RuntimeFlagsViewProtocol,
    settings: WallpaperSettings,
) -> Callable[[str], Awaitable[str | None]]:
    return build_remote_asset_url_validator(
        runtime_flags=runtime_flags,
        block_private_networks=settings.download.block_private_networks,
        dns_timeout_sec=settings.download.dns_timeout_sec,
        source="wallpaper download",
    )
