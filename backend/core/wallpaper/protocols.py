"""SoAI - WebUI wallpaper and guard protocol definitions [backend/core/wallpaper/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import httpx2

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict

__all__ = (
    "AuthGuardProtocol",
    "WallpaperManagerProtocol",
)


class AuthGuardProtocol(Protocol):

    async def is_throttled(self, identifier: str) -> tuple[bool, int | None]: ...

    async def register_failure(self, identifier: str) -> tuple[bool, int | None]: ...

    async def reset(self, identifier: str) -> None: ...


class WallpaperManagerProtocol(Protocol):

    async def get_current_wallpaper_info(
        self,
    ) -> tuple[str | None, float | None]: ...

    async def get_current_wallpaper_details(
        self,
    ) -> tuple[str | None, float | None, JSONDict | None]: ...

    async def set_wallpaper_from_staged_file(
        self,
        *,
        staged_file_path: str,
        original_filename: str,
        content_type: str | None,
        declared_size_bytes: int | None,
        cancellation_token: CancellationTokenProtocol,
    ) -> None: ...

    async def set_wallpaper_from_url(
        self,
        url: str,
        http_client: httpx2.AsyncClient,
        cancellation_id: str,
    ) -> None: ...

    async def delete_wallpaper(self) -> None: ...
