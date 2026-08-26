"""SoAI - CSV export API routes [backend/features/api/routes/metrics/metrics_export_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request
from fastapi.responses import StreamingResponse

from core.files.export import validate_export_time_window
from core.metrics.export import (
    build_metrics_history_filename,
    iter_metrics_history_csv_bytes,
)
from core.state.access import AccessAction
from features.api.routes.csv_streaming_response import build_csv_export_stream_response
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.query_parameters import require_supported_query_parameters

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.metrics.get(
        "/export",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def export_metrics_history_csv(
        request: Request,
        start_ts_ms: int | None = Query(default=None, ge=0),
        end_ts_ms: int | None = Query(default=None, ge=0),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> StreamingResponse:
        log_audit_event(request, "EXPORT_METRICS_HISTORY", "csv")
        require_supported_query_parameters(
            request,
            allowed_keys={"start_ts_ms", "end_ts_ms"},
        )
        validate_export_time_window(
            page_size=1,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        filename = build_metrics_history_filename()
        csv_bytes = iter_metrics_history_csv_bytes(
            api_context.dependencies.database_metrics,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        return build_csv_export_stream_response(filename=filename, csv_bytes=csv_bytes)
