"""SoAI - Host system power management routes [backend/features/api/routes/system/system_power_host_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Body, Depends, Request

from core.errors.exceptions import ValidationError
from core.runtime.platform import get_runtime_platform
from core.state.access import AccessAction
from core.system.power_actions import build_power_terminal_action, resolve_power_action
from core.system.power_operations import PowerOperationAction
from features.api.routes.system.system_power_acceptance import accept_power_operation
from features.api.routes.system.system_power_models import (
    AcceptedPowerOperationResponse,
)
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_action_not_supported, raise_forbidden
from features.api.schemas.system_actions import SystemActionRequest

__all__ = ("register_host_power_routes",)


async def _handle_host_power_action(
    request: Request,
    api_context: ApiContext,
    power_action: PowerOperationAction,
    payload: SystemActionRequest,
) -> AcceptedPowerOperationResponse:
    payload_view = payload.model_dump()
    log_audit_event(
        request,
        power_action.value.upper(),
        "host_system",
        payload_view,
    )
    if api_context.dependencies.runtime_flags.host_system_actions_disabled:
        raise_forbidden(
            request,
            "Host power actions are disabled because host system actions are disabled.",
            error_type="action_not_supported",
        )
    runtime_platform = get_runtime_platform()
    try:
        build_power_terminal_action(
            resolve_power_action(power_action),
            force=payload.force,
            is_windows=runtime_platform.is_windows,
            is_linux=runtime_platform.is_linux,
            is_macos=runtime_platform.is_macos,
        )
    except ValidationError as exception:
        raise_action_not_supported(request, str(exception))
    operation = await accept_power_operation(
        request,
        api_context,
        action=power_action,
        force=payload.force,
        delay_ms=payload.delay,
    )
    return AcceptedPowerOperationResponse(
        status="accepted",
        operation_id=operation.operation_id,
        action=operation.action,
        execute_at_ms=operation.execute_at_ms,
    )


def register_host_power_routes(routers: ApiRouters) -> None:
    @routers.system.post(
        "/power/shutdown",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.SYSTEM_POWER),
    )
    async def shutdown_host_system(
        request: Request,
        payload: SystemActionRequest = Body(
            default_factory=lambda: SystemActionRequest(delay=0, force=False),
        ),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AcceptedPowerOperationResponse:
        return await _handle_host_power_action(
            request, api_context, PowerOperationAction.HOST_SHUTDOWN, payload
        )

    @routers.system.post(
        "/power/reboot",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.SYSTEM_POWER),
    )
    async def reboot_host_system(
        request: Request,
        payload: SystemActionRequest = Body(
            default_factory=lambda: SystemActionRequest(delay=0, force=False),
        ),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AcceptedPowerOperationResponse:
        return await _handle_host_power_action(
            request, api_context, PowerOperationAction.HOST_REBOOT, payload
        )

    @routers.system.post(
        "/power/suspend",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.SYSTEM_POWER),
    )
    async def suspend_host_system(
        request: Request,
        payload: SystemActionRequest = Body(
            default_factory=lambda: SystemActionRequest(delay=0, force=False),
        ),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AcceptedPowerOperationResponse:
        return await _handle_host_power_action(
            request, api_context, PowerOperationAction.HOST_SUSPEND, payload
        )

    @routers.system.post(
        "/power/hibernate",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.SYSTEM_POWER),
    )
    async def hibernate_host_system(
        request: Request,
        payload: SystemActionRequest = Body(
            default_factory=lambda: SystemActionRequest(delay=0, force=False),
        ),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AcceptedPowerOperationResponse:
        return await _handle_host_power_action(
            request, api_context, PowerOperationAction.HOST_HIBERNATE, payload
        )
