"""SoAI - Hardware capabilities routes [backend/features/api/routes/hardware/hardware_capabilities_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.hardware.gpu_operation_results import (
    extract_gpu_operation_error_detail,
    extract_gpu_operation_error_message,
)
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.validation.runtime import is_success_payload
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import resolve_api_context
from features.api.runtime.errors import raise_server_error

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.hardware_capabilities_routes"


async def _system_capabilities_initial_state(request: Request) -> JSONDict:
    api_context = resolve_api_context(request)
    return await api_context.dependencies.hw_manager.get_system_capabilities()


def register_routes(routers: ApiRouters) -> None:
    @routers.hardware.get(
        "/capabilities",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )
    async def get_system_capabilities(request: Request) -> Response:
        snapshot = await _system_capabilities_initial_state(request)
        return JSONResponse(content=snapshot)

    async def _gpu_capabilities_initial_state(request: Request) -> JSONDict:
        api_context = resolve_api_context(request)
        caps = await api_context.dependencies.hw_manager.get_gpu_capabilities()
        if not is_success_payload(
            caps,
            get_logger(LOGGER_NAME),
            operation="api_hardware.capabilities.is_success_payload",
            recover_message="Failed to parse hardware capability success flag (non-critical).",
        ):
            raise_server_error(
                request,
                extract_gpu_operation_error_message(
                    caps,
                    default_message="Failed to get GPU capabilities.",
                ),
                error_type="gpu_error",
                extra=extract_gpu_operation_error_detail(caps),
            )
        return caps

    @routers.hardware.get(
        "/gpu/capabilities",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )
    async def get_gpu_capabilities(request: Request) -> Response:
        snapshot = await _gpu_capabilities_initial_state(request)
        return JSONResponse(content=snapshot)
