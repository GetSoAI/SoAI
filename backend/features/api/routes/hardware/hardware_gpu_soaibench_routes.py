"""SoAI - SoAIBench GPU API routes [backend/features/api/routes/hardware/hardware_gpu_soaibench_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from core.hardware.soaibench_limits import SOAIBENCH_HISTORY_DEFAULT_LIMIT
from core.state.access import AccessAction
from features.api.routes.csv_streaming_response import build_csv_export_stream_response
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.query_parameters import require_supported_query_parameters
from features.api.schemas.hardware import GPUSoAIBenchStartRequest

__all__ = (
    "export_soaibench_history_csv_api",
    "get_soaibench_run_api",
    "list_soaibench_history_api",
    "register_endpoints",
    "register_routes",
    "start_soaibench_run_api",
    "stop_soaibench_run_api",
)


async def start_soaibench_run_api(
    request: Request,
    payload: GPUSoAIBenchStartRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await api_context.dependencies.hardware_soaibench.start_run(
        device_id=payload.device_id,
        profile=payload.profile,
        benchmark_mode=payload.benchmark_mode,
        temperature_limit_celsius=payload.temperature_limit_celsius,
        created_by_user_id=current_user["id"],
        created_by_tool="hardware_api",
    )
    log_audit_event(
        request,
        "START_GPU_SOAIBENCH",
        f"gpu_device:{payload.device_id}",
        {
            "benchmark_mode": payload.benchmark_mode,
            "device_id": payload.device_id,
            "profile": payload.profile,
        },
    )
    return JSONResponse(content=result)


async def get_soaibench_run_api(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await api_context.dependencies.hardware_soaibench.get_run(
        run_id=run_id,
        user_id=current_user["id"],
    )
    return JSONResponse(content=result)


async def stop_soaibench_run_api(
    request: Request,
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await api_context.dependencies.hardware_soaibench.stop_run(
        run_id=run_id,
        user_id=current_user["id"],
    )
    log_audit_event(
        request,
        "STOP_GPU_SOAIBENCH",
        f"soaibench_run:{run_id}",
        {"run_id": run_id},
    )
    return JSONResponse(content=result)


async def list_soaibench_history_api(
    device_id: str = Query(...),
    limit: int = Query(SOAIBENCH_HISTORY_DEFAULT_LIMIT),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await api_context.dependencies.hardware_soaibench.list_history(
        device_id=device_id,
        user_id=current_user["id"],
        limit=limit,
    )
    return JSONResponse(content=result)


async def export_soaibench_history_csv_api(
    request: Request,
    device_id: str = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> StreamingResponse:
    require_supported_query_parameters(request, allowed_keys={"device_id"})
    log_audit_event(request, "EXPORT_GPU_SOAIBENCH_HISTORY", f"gpu_device:{device_id}")
    filename, csv_bytes = await api_context.dependencies.hardware_soaibench.export_history_csv(
        device_id=device_id,
        user_id=current_user["id"],
    )
    return build_csv_export_stream_response(filename=filename, csv_bytes=csv_bytes)


def register_endpoints(router: APIRouter) -> None:
    router.post(
        "/gpu/soaibench/runs",
        dependencies=require_action_dependencies(AccessAction.HW_GPU_TUNING),
    )(start_soaibench_run_api)
    router.get(
        "/gpu/soaibench/runs/{run_id}",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )(get_soaibench_run_api)
    router.post(
        "/gpu/soaibench/runs/{run_id}/stop",
        dependencies=require_action_dependencies(AccessAction.RECOVERY_ADMIN),
    )(stop_soaibench_run_api)
    router.get(
        "/gpu/soaibench/runs",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )(list_soaibench_history_api)
    router.get(
        "/gpu/soaibench/history/export",
        dependencies=require_action_dependencies(AccessAction.HARDWARE_READ),
    )(export_soaibench_history_csv_api)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.hardware)
