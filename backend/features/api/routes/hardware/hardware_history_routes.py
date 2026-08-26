"""SoAI - Hardware history HTTP endpoint [backend/features/api/routes/hardware/hardware_history_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.hardware.history_selection import parse_hardware_history_query_selection
from core.history.request.query import build_history_query
from core.state.access import AccessAction
from features.api.routes.hardware.hardware_history_data_loading import (
    load_hardware_history_data,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import resolve_api_context
from features.api.runtime.errors import raise_invalid_request
from features.api.runtime.query_parameters import require_supported_query_parameters

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

_HARDWARE_HISTORY_MAX_TIMESTAMP_MS = 4_102_444_800_000
_HARDWARE_HISTORY_MAX_INTERVAL_MS = 86_400_000


def _parse_history_request(
    request: Request,
    *,
    component_value: str | None = None,
    gpu_index_value: int | None = None,
    identifier_value: str | None = None,
) -> tuple[str, int | None, str | None]:
    try:
        selection = parse_hardware_history_query_selection(
            component_value=(
                component_value
                if component_value is not None
                else request.query_params.get("component")
            ),
            gpu_index_value=gpu_index_value,
            gpu_index_raw_value=request.query_params.get("gpu_index"),
            identifier_value=(
                identifier_value
                if identifier_value is not None
                else request.query_params.get("identifier")
            ),
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    return (selection.component or "", selection.gpu_index, selection.identifier)


async def _hardware_history_initial_state(request: Request) -> JSONDict:
    api_context = resolve_api_context(request)
    hw_mgr = api_context.dependencies.hw_manager
    component, gpu_index, identifier = _parse_history_request(request)
    history_params = request.query_params
    history_request = build_history_query(
        {
            "start_ts_ms": history_params.get("start_ts_ms"),
            "end_ts_ms": history_params.get("end_ts_ms"),
            "points": history_params.get("points"),
            "interval_ms": history_params.get("interval_ms"),
            "aggregation": history_params.get("aggregation"),
        },
        hw_mgr.history_config,
    )
    return await load_hardware_history_data(
        hardware_manager=hw_mgr,
        history_request=history_request,
        component=component,
        gpu_index=gpu_index,
        identifier=identifier,
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.hardware.get(
        "/history",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )
    async def get_hardware_history(
        request: Request,
        component: str | None = Query(None),
        start_ts_ms: int | None = Query(None, ge=0, le=_HARDWARE_HISTORY_MAX_TIMESTAMP_MS),
        end_ts_ms: int | None = Query(None, ge=0, le=_HARDWARE_HISTORY_MAX_TIMESTAMP_MS),
        gpu_index: int | None = Query(None, ge=0),
        points: int = Query(300, ge=1, le=25000),
        interval_ms: int | None = Query(None, ge=1, le=_HARDWARE_HISTORY_MAX_INTERVAL_MS),
        aggregation: Literal["avg", "min", "max", "ohlc"] = Query("avg"),
    ) -> Response:
        allowed_keys = {
            "component",
            "start_ts_ms",
            "end_ts_ms",
            "gpu_index",
            "points",
            "interval_ms",
            "aggregation",
            "identifier",
        }
        require_supported_query_parameters(request, allowed_keys=allowed_keys)
        _parse_history_request(
            request,
            component_value=component,
            gpu_index_value=gpu_index,
            identifier_value=request.query_params.get("identifier"),
        )
        build_history_query(
            {
                "start_ts_ms": start_ts_ms,
                "end_ts_ms": end_ts_ms,
                "points": points,
                "interval_ms": interval_ms,
                "aggregation": aggregation,
            },
            resolve_api_context(request).dependencies.hw_manager.history_config,
        )
        initial_state = await _hardware_history_initial_state(request)
        return JSONResponse(content=initial_state)
