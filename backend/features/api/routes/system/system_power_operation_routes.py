"""SoAI - Durable power operation query and cancellation routes [backend/features/api/routes/system/system_power_operation_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.state.access import AccessAction
from features.api.routes.system.system_power_models import (
    PowerOperationResponse,
    build_power_operation_response,
)
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_not_found

__all__ = ("register_power_operation_routes",)


def register_power_operation_routes(routers: ApiRouters) -> None:
    read_dependencies = require_action_dependencies(AccessAction.SYSTEM_POWER)

    @routers.system.get(
        "/power/operations/active",
        dependencies=read_dependencies,
    )
    async def get_active_power_operation(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        operation = await api_context.dependencies.power_operation_supervisor.get_active()
        content = (
            None if operation is None else build_power_operation_response(operation).model_dump()
        )
        return JSONResponse(content=content)

    @routers.system.get(
        "/power/operations/{operation_id}",
        response_model=PowerOperationResponse,
        dependencies=read_dependencies,
    )
    async def get_power_operation(
        request: Request,
        operation_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> PowerOperationResponse:
        operation = await api_context.dependencies.power_operation_supervisor.get(operation_id)
        if operation is None:
            raise_not_found(request, "Power operation was not found.")
        return build_power_operation_response(operation)

    @routers.system.post(
        "/power/operations/{operation_id}/cancel",
        status_code=202,
        response_model=PowerOperationResponse,
        dependencies=restart_protected_dependencies(AccessAction.SYSTEM_POWER),
    )
    async def cancel_power_operation(
        request: Request,
        operation_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> PowerOperationResponse:
        operation = await api_context.dependencies.power_operation_supervisor.cancel(operation_id)
        log_audit_event(
            request,
            "CANCEL_POWER_OPERATION",
            operation.operation_id,
            {"action": operation.action.value},
        )
        return build_power_operation_response(operation)
