"""SoAI - Application power management routes [backend/features/api/routes/system/system_power_application_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Body, Depends, Request

from core.state.access import AccessAction
from core.system.power_operations import PowerOperationAction
from features.api.routes.system.system_power_acceptance import accept_power_operation
from features.api.routes.system.system_power_models import (
    AcceptedPowerOperationResponse,
)
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.system_actions import ApplicationPowerActionRequest

__all__ = ("register_application_power_routes",)


def _default_application_power_action_request() -> ApplicationPowerActionRequest:
    return ApplicationPowerActionRequest(delay=0)


def register_application_power_routes(routers: ApiRouters) -> None:
    @routers.system.post(
        "/power/restart-application",
        status_code=202,
        response_model=AcceptedPowerOperationResponse,
        dependencies=restart_protected_dependencies(AccessAction.SYSTEM_POWER),
    )
    async def restart_soai_application(
        request: Request,
        payload: ApplicationPowerActionRequest = Body(
            default_factory=_default_application_power_action_request,
        ),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AcceptedPowerOperationResponse:
        log_audit_event(request, "RESTART_APPLICATION", "soai_core")
        operation = await accept_power_operation(
            request,
            api_context,
            action=PowerOperationAction.APPLICATION_RESTART,
            force=False,
            delay_ms=payload.delay,
        )
        return AcceptedPowerOperationResponse(
            status="accepted",
            operation_id=operation.operation_id,
            action=operation.action,
            execute_at_ms=operation.execute_at_ms,
        )

    @routers.system.post(
        "/power/shutdown-application",
        status_code=202,
        response_model=AcceptedPowerOperationResponse,
        dependencies=restart_protected_dependencies(AccessAction.SYSTEM_POWER),
    )
    async def shutdown_soai_application(
        request: Request,
        payload: ApplicationPowerActionRequest = Body(
            default_factory=_default_application_power_action_request,
        ),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AcceptedPowerOperationResponse:
        log_audit_event(request, "SHUTDOWN_APPLICATION", "soai_core")
        operation = await accept_power_operation(
            request,
            api_context,
            action=PowerOperationAction.APPLICATION_SHUTDOWN,
            force=False,
            delay_ms=payload.delay,
        )
        return AcceptedPowerOperationResponse(
            status="accepted",
            operation_id=operation.operation_id,
            action=operation.action,
            execute_at_ms=operation.execute_at_ms,
        )
