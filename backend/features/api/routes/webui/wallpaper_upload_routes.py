"""SoAI - Wallpaper upload routes [backend/features/api/routes/webui/wallpaper_upload_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.state.access import AccessAction
from core.wallpaper.settings import resolve_wallpaper_settings
from features.api.routes.webui.wallpaper_tasks import (
    create_wallpaper_update_task,
)
from features.api.routes.webui.wallpaper_upload_flow import (
    execute_wallpaper_upload_flow,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/wallpaper/upload",
        status_code=200,
        dependencies=require_action_dependencies(AccessAction.WEBUI_APPEARANCE_ADMIN),
    )
    async def upload_wallpaper(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        registry, task = await create_wallpaper_update_task(
            request=request,
            api_context=api_context,
            status_message="Uploading wallpaper",
            metadata={"operation": "wallpaper_upload", "filename": ""},
        )
        log_audit_event(request, "UPLOAD_WALLPAPER", "wallpaper")
        settings = resolve_wallpaper_settings(api_context.dependencies.config)
        return await execute_wallpaper_upload_flow(
            request=request,
            api_context=api_context,
            registry=registry,
            task=task,
            settings=settings,
        )
