"""SoAI - System plugin circuit breaker routes [backend/features/api/routes/system/system_plugins_circuit_breaker_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.events.types_plugins import ClearQuarantineCommand
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.plugin_compatibility import get_validated_plugin_name

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


async def _get_circuit_breaker_snapshot(request: Request, api_context: ApiContext) -> JSONDict:
    plugin_name = request.path_params["plugin_name"]
    normalized_name = await get_validated_plugin_name(request, plugin_name)
    orchestrator_instance = api_context.dependencies.orchestrator_lifecycle
    snapshot = await orchestrator_instance.circuit_breakers.get_circuit_breaker_snapshot(
        normalized_name,
    )
    return snapshot


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/plugins/{plugin_name}/check-circuit-breaker",
        dependencies=require_action_dependencies(AccessAction.PLUGIN_READ),
    )
    async def check_plugin_circuit_breaker(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        snapshot = await _get_circuit_breaker_snapshot(request, api_context)
        return JSONResponse(content=snapshot)

    @routers.system.post(
        "/plugins/{plugin_name}/reset-circuit-breaker",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )
    async def reset_plugin_circuit_breaker(
        request: Request,
        normalized_name: str = Depends(get_validated_plugin_name),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
            request,
            ClearQuarantineCommand,
            "final",
            "RESET_CIRCUIT_BREAKER",
            normalized_name,
            {
                "display_name": await api_context.dependencies.plugin_manager.get_plugin_display_name(
                    normalized_name,
                ),
            },
            {"plugin_name": normalized_name},
        )
