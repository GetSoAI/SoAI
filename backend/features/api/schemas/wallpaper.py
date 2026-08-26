"""SoAI - Wallpaper API schemas [backend/features/api/schemas/wallpaper.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel

__all__ = (
    "WallpaperDownloadRequest",
    "WallpaperInfoResponse",
    "WallpaperMetadata",
)


class WallpaperDownloadRequest(BaseModel):
    url: AnyHttpUrl


class WallpaperMetadata(BaseModel):
    type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None


class WallpaperInfoResponse(BaseModel):
    exists: bool
    url: AnyHttpUrl | None = None
    metadata: WallpaperMetadata | None = None
