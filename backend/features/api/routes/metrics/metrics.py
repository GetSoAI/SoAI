"""SoAI - Metrics API routes [backend/features/api/routes/metrics/metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.history.request.query import build_history_query
from core.state.access import AccessAction
from features.api.routes.metrics.metrics_allowed_keys import METRICS_QUERY_ALLOWED_KEYS
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.metrics_history_payload import load_metrics_history_payload
from features.api.runtime.query_parameters import require_supported_query_parameters

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.metrics.get("", dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE))
    async def get_system_metrics(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        metrics = await api_context.dependencies.metrics_manager.get_all_metrics()
        return JSONResponse(content=metrics)

    @routers.metrics.get(
        "/capabilities",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def get_metrics_capabilities(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        capabilities = await api_context.dependencies.metrics_manager.get_capabilities()
        return JSONResponse(content=capabilities)

    @routers.system.post(
        "/metrics/reset",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.METRICS_RESET),
    )
    async def reset_all_metrics(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_audit_event(request, "RESET_METRICS", "all")
        await api_context.dependencies.metrics_manager.reset_metrics()
        return JSONResponse(
            status_code=202,
            content={
                "message": (
                    "In-memory metrics and live persistence reset. Historical time-series "
                    "data preserved."
                ),
            },
        )

    async def _get_metrics_history_initial_state(
        api_context: ApiContext,
        metric_key: str,
        start_ts_ms: int | None,
        end_ts_ms: int | None,
        points: int,
        interval_ms: int | None,
        aggregation: Literal["avg", "min", "max", "count", "delta", "ohlc", "delta_ohlc"],
    ) -> JSONDict:
        metrics_mgr = api_context.dependencies.metrics_manager
        params: JSONDict = {
            "start_ts_ms": start_ts_ms,
            "end_ts_ms": end_ts_ms,
            "points": points,
            "interval_ms": interval_ms,
            "aggregation": aggregation,
        }
        history_request = build_history_query(params, metrics_mgr.history_config)
        return await load_metrics_history_payload(metrics_mgr, metric_key, history_request)

    @routers.metrics.get(
        "/history",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def get_metrics_history(
        request: Request,
        metric_key: str,
        api_context: ApiContext = Depends(resolve_api_context),
        start_ts_ms: int | None = None,
        end_ts_ms: int | None = None,
        points: int = Query(300, ge=1, le=25000),
        interval_ms: int | None = Query(None, ge=1),
        aggregation: Literal["avg", "min", "max", "count", "delta", "ohlc", "delta_ohlc"] = Query(
            "avg",
        ),
    ) -> Response:
        require_supported_query_parameters(request, allowed_keys=METRICS_QUERY_ALLOWED_KEYS)
        payload = await _get_metrics_history_initial_state(
            api_context,
            metric_key,
            start_ts_ms,
            end_ts_ms,
            points,
            interval_ms,
            aggregation,
        )
        return JSONResponse(content=payload)
