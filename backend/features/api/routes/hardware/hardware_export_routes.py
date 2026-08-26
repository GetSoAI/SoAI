"""SoAI - Hardware history export routes [backend/features/api/routes/hardware/hardware_export_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request
from fastapi.responses import StreamingResponse

from core.files.export import validate_export_time_window
from core.hardware.export import (
    build_hardware_history_filename,
    iter_hardware_history_csv_bytes,
)
from core.hardware.history_selection import normalize_hardware_history_export_selection
from core.state.access import AccessAction
from features.api.routes.csv_streaming_response import build_csv_export_stream_response
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.query_parameters import require_supported_query_parameters

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.hardware.get(
        "/export",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )
    async def export_hardware_history_csv(
        request: Request,
        start_ts_ms: int | None = Query(default=None, ge=0),
        end_ts_ms: int | None = Query(default=None, ge=0),
        component: str | None = Query(default=None),
        identifier: str | None = Query(default=None),
        gpu_index: int | None = Query(default=None, ge=0),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> StreamingResponse:
        log_audit_event(request, "EXPORT_HARDWARE_HISTORY", "csv")
        require_supported_query_parameters(
            request,
            allowed_keys={"start_ts_ms", "end_ts_ms", "component", "identifier", "gpu_index"},
        )
        validate_export_time_window(
            page_size=1,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        selection = normalize_hardware_history_export_selection(
            component=component,
            identifier=identifier,
            gpu_index=gpu_index,
        )
        filename = build_hardware_history_filename()
        csv_bytes = iter_hardware_history_csv_bytes(
            api_context.dependencies.database_hardware,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            component=selection.component,
            identifier=selection.identifier,
            gpu_index=selection.gpu_index,
        )
        return build_csv_export_stream_response(filename=filename, csv_bytes=csv_bytes)
