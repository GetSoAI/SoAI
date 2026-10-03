"""SoAI - System log snapshot route [backend/features/api/routes/system/system_logs_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.runtime.request_trace_id import get_request_trace_id
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_not_found, raise_service_unavailable

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.system_logs_routes"
OPERATION_LOGS_SNAPSHOT = "api_system.logs.snapshot"


async def get_log_sources(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    log_manager = api_context.dependencies.log_manager
    if log_manager is None:
        raise_service_unavailable(request, "Logging service is unavailable.")
    return JSONResponse(content={"sources": log_manager.list_log_sources()})


async def get_logs_snapshot(
    request: Request,
    source_name: str,
    limit: int = Query(200, ge=1, le=10000),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    log_manager = api_context.dependencies.log_manager
    if log_manager is None:
        raise_service_unavailable(request, "Logging service is unavailable.")
    try:
        entries = await asyncio.to_thread(log_manager.get_recent_logs, source_name, limit)
    except (ValidationError, ValueError) as error:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Log source lookup failed.",
            operation=OPERATION_LOGS_SNAPSHOT,
            trace_id=get_request_trace_id(request),
            level="debug",
        )
        raise_not_found(request, "Log source unavailable. Choose an available log source.")
    return JSONResponse(content={"entries": entries, "source": source_name, "limit": limit})


def register_routes(routers: ApiRouters) -> None:
    routers.system.add_api_route(
        "/logs/sources",
        get_log_sources,
        methods=["GET"],
        dependencies=require_action_dependencies(AccessAction.LOG_ACCESS),
    )
    routers.system.add_api_route(
        "/logs/{source_name}",
        get_logs_snapshot,
        methods=["GET"],
        dependencies=require_action_dependencies(AccessAction.LOG_ACCESS),
    )
