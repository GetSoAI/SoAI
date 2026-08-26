"""SoAI - Wallpaper delete routes [backend/features/api/routes/webui/wallpaper_delete_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, Response

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_webui import WallpaperChangedEvent
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.webui.wallpaper_error_handling import (
    handle_wallpaper_exception,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_request_trace_id,
    resolve_api_context,
)
from features.api.runtime.responses import create_no_content_response

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.wallpaper_delete_routes"
OPERATION = "webui.wallpaper.delete"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.delete(
        "/wallpaper",
        status_code=204,
        dependencies=require_action_dependencies(AccessAction.WEBUI_APPEARANCE_ADMIN),
    )
    async def delete_wallpaper(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_audit_event(request, "DELETE_WALLPAPER", "current_wallpaper")
        try:
            await api_context.dependencies.webui_manager.wallpaper.delete_wallpaper()
            await api_context.dependencies.event_bus.publish(WallpaperChangedEvent())
            return create_no_content_response()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Wallpaper deletion failed.",
                trace_id=get_request_trace_id(request),
                operation=OPERATION,
                level="warning",
            )
            handle_wallpaper_exception(request, exception, "wallpaper deletion")
