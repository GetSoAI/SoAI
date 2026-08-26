"""SoAI - System log snapshot route [backend/features/api/routes/system/system_logs_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_not_found, raise_service_unavailable

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/logs/sources",
        dependencies=require_action_dependencies(AccessAction.LOG_ACCESS),
    )
    async def get_log_sources(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_manager = api_context.dependencies.log_manager
        if log_manager is None:
            raise_service_unavailable(
                request,
                "Logging service is unavailable.",
            )
        return JSONResponse(content={"sources": log_manager.list_log_sources()})

    @routers.system.get(
        "/logs/{source_name}",
        dependencies=require_action_dependencies(AccessAction.LOG_ACCESS),
    )
    async def get_logs_snapshot(
        request: Request,
        source_name: str,
        limit: int = Query(200, ge=1, le=10000),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_manager = api_context.dependencies.log_manager
        if log_manager is None:
            raise_service_unavailable(
                request,
                "Logging service is unavailable.",
            )
        try:
            entries = await asyncio.to_thread(log_manager.get_recent_logs, source_name, limit)
        except (ValidationError, ValueError) as error:
            raise_not_found(request, str(error))
        return JSONResponse(content={"entries": entries, "source": source_name, "limit": limit})
