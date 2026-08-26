"""SoAI - Hardware snapshot HTTP endpoint [backend/features/api/routes/hardware/hardware_snapshot_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.state.access import AccessAction
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import resolve_api_context

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


def _parse_components(value: str | None) -> list[str] | None:
    if value is None:
        return None
    components = [item.strip() for item in value.split(",") if item.strip()]
    return components or None


async def _hardware_snapshot_initial_state(
    request: Request,
    *,
    components: list[str] | None,
    cache: bool,
) -> JSONDict:
    api_context = resolve_api_context(request)
    return await api_context.dependencies.hw_manager.get_system_info(
        components=components,
        cache=cache,
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.hardware.get(
        "/snapshot",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )
    async def get_hardware_snapshot(
        request: Request,
        components: str | None = Query(default=None),
        cache: bool = Query(default=True),
    ) -> Response:
        snapshot = await _hardware_snapshot_initial_state(
            request,
            components=_parse_components(components),
            cache=cache,
        )
        return JSONResponse(content=snapshot)
