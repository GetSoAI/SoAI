"""SoAI - Wallpaper read routes [backend/features/api/routes/webui/wallpaper_read_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import pydantic
from fastapi import Depends, Request, Response
from fastapi.responses import FileResponse
from pydantic import AnyHttpUrl, TypeAdapter
from starlette.datastructures import URL

from core.filesystem.async_queries import async_path_exists
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_not_found, raise_server_error
from features.api.schemas.wallpaper import WallpaperInfoResponse, WallpaperMetadata

__all__ = ("register_routes",)

_WALLPAPER_CACHE_MAX_AGE_SECONDS = 31_536_000


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/wallpaper", response_model=WallpaperInfoResponse)
    async def get_wallpaper_info(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> WallpaperInfoResponse:
        _, mtime, metadata = (
            await api_context.dependencies.webui_manager.wallpaper.get_current_wallpaper_details()
        )
        if mtime is not None:
            wallpaper_url = URL(str(request.url_for("serve_wallpaper_file"))).include_query_params(
                v=int(mtime),
            )
            try:
                url_value = TypeAdapter(AnyHttpUrl).validate_python(str(wallpaper_url))
            except pydantic.ValidationError:
                raise_server_error(
                    request,
                    "Wallpaper URL is invalid.",
                )
            if metadata is None:
                metadata_value = None
            else:
                try:
                    metadata_value = WallpaperMetadata.model_validate(metadata)
                except pydantic.ValidationError:
                    raise_server_error(
                        request,
                        "Wallpaper metadata is invalid.",
                    )
            return WallpaperInfoResponse(exists=True, url=url_value, metadata=metadata_value)
        return WallpaperInfoResponse(exists=False, url=None, metadata=None)

    @routers.webui.get("/wallpaper_file", include_in_schema=False)
    async def serve_wallpaper_file(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        filepath, _ = (
            await api_context.dependencies.webui_manager.wallpaper.get_current_wallpaper_info()
        )
        if filepath and await async_path_exists(filepath):
            headers = {
                "Cache-Control": (f"public, max-age={_WALLPAPER_CACHE_MAX_AGE_SECONDS}, immutable"),
                "X-Content-Type-Options": "nosniff",
            }
            return FileResponse(filepath, headers=headers)
        raise_not_found(
            request,
            "Wallpaper file not found.",
            error_type="not_found_error",
        )
