"""SoAI - Wallpaper settings resolution helpers [backend/core/wallpaper/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.byte_sizes import require_config_mib_to_bytes
from core.config.numeric_lenient import coerce_lenient_bounded_float
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ConfigurationError

__all__ = (
    "WallpaperDownloadSettings",
    "WallpaperSettings",
    "resolve_wallpaper_settings",
)


@dataclass(frozen=True, slots=True)
class WallpaperDownloadSettings:
    block_private_networks: bool
    dns_timeout_sec: float
    max_redirects: int


@dataclass(frozen=True, slots=True)
class WallpaperSettings:
    max_size_bytes: int
    storage_path: str
    temp_path: str | None
    download: WallpaperDownloadSettings


def _resolve_wallpaper_max_size_bytes(config: ConfigProtocol) -> int:
    return require_config_mib_to_bytes(
        config.get("SERVER.WEBUI.WALLPAPER_MAX_SIZE_MB"),
        field="SERVER.WEBUI.WALLPAPER_MAX_SIZE_MB",
        missing_message="SERVER.WEBUI.WALLPAPER_MAX_SIZE_MB is missing in config.yaml.",
        invalid_message="SERVER.WEBUI.WALLPAPER_MAX_SIZE_MB must be a valid integer in config.yaml.",
        positive_message="SERVER.WEBUI.WALLPAPER_MAX_SIZE_MB must be greater than zero.",
    )


def _resolve_wallpaper_storage_path(config: ConfigProtocol) -> str:
    wallpaper_storage_path = config.get_str("SERVER.WEBUI.WALLPAPER_STORAGE_PATH")
    if wallpaper_storage_path is None or not wallpaper_storage_path.strip():
        raise ConfigurationError(
            "SERVER.WEBUI.WALLPAPER_STORAGE_PATH is missing or invalid in config.yaml.",
        )
    return wallpaper_storage_path.strip()


def _resolve_temp_path(config: ConfigProtocol) -> str | None:
    temp_path_raw = config.get_str("SYSTEM.PATHS.TEMP")
    if temp_path_raw is None:
        return None
    stripped = temp_path_raw.strip()
    if not stripped:
        return None
    return stripped


def _resolve_wallpaper_download_settings(
    config: ConfigProtocol,
) -> WallpaperDownloadSettings:
    max_redirects = config.get_int("SERVER.WEBUI.WALLPAPER_DOWNLOAD.MAX_REDIRECTS")
    return WallpaperDownloadSettings(
        block_private_networks=config.get_bool(
            "SERVER.WEBUI.WALLPAPER_DOWNLOAD.BLOCK_PRIVATE_NETWORKS",
        ),
        dns_timeout_sec=coerce_lenient_bounded_float(
            config.get("SERVER.WEBUI.WALLPAPER_DOWNLOAD.DNS_TIMEOUT_SEC"),
            default=3.0,
            minimum=0.5,
            maximum=30.0,
        ),
        max_redirects=max(0, min(max_redirects, 25)),
    )


def resolve_wallpaper_settings(config: ConfigProtocol) -> WallpaperSettings:
    return WallpaperSettings(
        max_size_bytes=_resolve_wallpaper_max_size_bytes(config),
        storage_path=_resolve_wallpaper_storage_path(config),
        temp_path=_resolve_temp_path(config),
        download=_resolve_wallpaper_download_settings(config),
    )
