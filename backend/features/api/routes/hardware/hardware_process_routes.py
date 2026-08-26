"""SoAI - Hardware process routes [backend/features/api/routes/hardware/hardware_process_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.state.access import AccessAction
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_action_failed
from features.api.schemas.hardware import KillProcessRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


async def _process_list_snapshot(request: Request) -> list[JSONDict]:
    filter_str = request.query_params.get("filter")
    api_context = resolve_api_context(request)
    process_list = await api_context.dependencies.terminal.get_process_list(filter_str=filter_str)
    return process_list or []


def register_routes(routers: ApiRouters) -> None:
    @routers.hardware.get(
        "/processes",
        dependencies=require_action_dependencies(AccessAction.HW_PROCESS_VIEW),
    )
    async def list_processes(request: Request) -> Response:
        snapshot = await _process_list_snapshot(request)
        return JSONResponse(content=snapshot)

    @routers.actions.post(
        "/processes/{pid}/kill",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.RECOVERY_ADMIN),
    )
    async def kill_process(
        request: Request,
        pid: int,
        payload: KillProcessRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_audit_event(
            request,
            "KILL_PROCESS",
            f"pid:{pid}",
            {"signal": payload.signal, "use_sudo": payload.use_sudo},
        )
        success, message = await api_context.dependencies.terminal.kill_process(
            pid=pid,
            signal_to_send=payload.signal,
            use_sudo=payload.use_sudo,
        )
        if not success:
            raise_action_failed(request, message)
        return JSONResponse(content={"status": "success", "message": message})
