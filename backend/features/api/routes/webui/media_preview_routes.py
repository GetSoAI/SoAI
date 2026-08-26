"""SoAI - WebUI media proxy and link/text preview routes [backend/features/api/routes/webui/media_preview_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse

from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.webui.media_preview_error_translation import (
    MEDIA_PREVIEW_REMOTE_ROUTE_EXCEPTIONS,
    MEDIA_PREVIEW_SCREENSHOT_ROUTE_EXCEPTIONS,
    raise_for_media_preview_route_exception,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.media_preview_routes"
OPERATION_PROXY = "webui.media.proxy"
OPERATION_LINK_PREVIEW = "webui.media.link_preview"
OPERATION_TEXT_PREVIEW = "webui.media.text_preview"
OPERATION_PAGE_SCREENSHOT = "webui.media.page_screenshot"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/previews/proxy",
        dependencies=require_action_dependencies(AccessAction.WEB_SEARCH),
    )
    async def proxy_media(
        request: Request,
        url: str = Query(description="Remote http(s) URL to proxy"),
        download: int = Query(default=0, ge=0, le=1),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> FileResponse:
        logger = get_logger(LOGGER_NAME)
        try:
            proxy_file = (
                await api_context.dependencies.webui_manager.proxy_files.prepare_proxy_file(
                    api_context.dependencies.http_client,
                    api_context.dependencies.runtime_flags,
                    url,
                    download=int(download) == 1,
                )
            )
            return FileResponse(
                proxy_file.file_path,
                status_code=int(proxy_file.status_code),
                media_type=str(proxy_file.media_type),
                headers=dict(proxy_file.headers),
            )
        except MEDIA_PREVIEW_REMOTE_ROUTE_EXCEPTIONS as exception:
            raise_for_media_preview_route_exception(
                request=request,
                logger=logger,
                exception=exception,
                operation=OPERATION_PROXY,
                failure_message="Media proxy failed",
                translate_upstream_request_errors=True,
            )

    @routers.webui.get(
        "/previews/link_preview",
        dependencies=require_action_dependencies(AccessAction.WEB_SEARCH),
    )
    async def link_preview(
        request: Request,
        url: str = Query(description="Remote http(s) URL to preview"),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        logger = get_logger(LOGGER_NAME)
        try:
            preview = await api_context.dependencies.webui_manager.link_previews.get_link_preview(
                api_context.dependencies.http_client,
                api_context.dependencies.runtime_flags,
                url,
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "type": preview.type,
                    "title": preview.title,
                    "description": preview.description,
                    "thumbnail_url": preview.thumbnail_url,
                    "preview_url": preview.preview_url,
                    "embed_url": preview.embed_url,
                    "source_url": preview.source_url,
                    "download_url": preview.download_url,
                    "excerpt_available": preview.excerpt_available,
                },
            )
        except MEDIA_PREVIEW_REMOTE_ROUTE_EXCEPTIONS as exception:
            raise_for_media_preview_route_exception(
                request=request,
                logger=logger,
                exception=exception,
                operation=OPERATION_LINK_PREVIEW,
                failure_message="Link preview failed",
                translate_upstream_request_errors=True,
            )

    @routers.webui.get(
        "/previews/text_preview",
        dependencies=require_action_dependencies(AccessAction.WEB_SEARCH),
    )
    async def text_preview(
        request: Request,
        url: str = Query(description="Remote http(s) URL to fetch excerpt from"),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        logger = get_logger(LOGGER_NAME)
        try:
            preview = await api_context.dependencies.webui_manager.text_previews.get_text_preview(
                api_context.dependencies.http_client,
                api_context.dependencies.runtime_flags,
                url,
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "source_url": preview.source_url,
                    "final_url": preview.final_url,
                    "excerpt": preview.excerpt,
                    "content_type": preview.content_type,
                },
            )
        except MEDIA_PREVIEW_REMOTE_ROUTE_EXCEPTIONS as exception:
            raise_for_media_preview_route_exception(
                request=request,
                logger=logger,
                exception=exception,
                operation=OPERATION_TEXT_PREVIEW,
                failure_message="Text preview failed",
                translate_upstream_request_errors=True,
            )

    @routers.webui.get(
        "/previews/page_screenshot",
        dependencies=require_action_dependencies(AccessAction.WEB_SEARCH),
    )
    async def page_screenshot(
        request: Request,
        url: str = Query(description="Remote http(s) URL to capture screenshot for"),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> FileResponse:
        logger = get_logger(LOGGER_NAME)
        try:
            page_screenshots = api_context.dependencies.webui_manager.page_screenshots
            screenshot_file = await page_screenshots.prepare_page_screenshot_file(
                api_context.dependencies.runtime_flags,
                url,
            )
            return FileResponse(
                screenshot_file.file_path,
                status_code=int(screenshot_file.status_code),
                media_type=str(screenshot_file.media_type),
                headers=dict(screenshot_file.headers),
            )
        except MEDIA_PREVIEW_SCREENSHOT_ROUTE_EXCEPTIONS as exception:
            raise_for_media_preview_route_exception(
                request=request,
                logger=logger,
                exception=exception,
                operation=OPERATION_PAGE_SCREENSHOT,
                failure_message="Page screenshot failed",
                translate_upstream_request_errors=False,
            )
