"""SoAI - External provider create/list endpoints [backend/features/api/routes/plugins/plugin_provider_create_list_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.state.access import AccessAction
from features.api.routes.plugins.provider_lifecycle_operations import (
    create_external_provider,
)
from features.api.routes.plugins.provider_list_snapshot import get_provider_list_snapshot
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.plugins import ExternalProviderCreate

__all__ = ("register_routes",)


async def create_provider_for_plugin(
    request: Request,
    plugin_name: str,
    payload: ExternalProviderCreate,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    return await create_external_provider(
        request,
        plugin_name,
        payload,
        api_context.dependencies.model_provider_coordinator,
        api_context.dependencies.plugin_manager,
        api_context.dependencies.runtime_flags,
    )


async def provider_list_for_plugin(request: Request) -> Response:
    snapshot = await get_provider_list_snapshot(request)
    return JSONResponse(content=snapshot)


def register_routes(routers: ApiRouters) -> None:
    routers.plugins.post(
        "/{plugin_name}/providers",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )(create_provider_for_plugin)
    routers.plugins.get(
        "/{plugin_name}/providers",
        dependencies=require_action_dependencies(AccessAction.PLUGIN_ADMIN),
    )(provider_list_for_plugin)
