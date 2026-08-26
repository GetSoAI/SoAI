"""SoAI - Task cancellation registry routes [backend/features/api/routes/tasks/task_cancellation_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.events.types_tasks import CancelAllTasksCommand
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.tasks import CancelAllTasksPayload

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "cancel_all_tasks",
    "get_cancellation_registry_snapshot",
    "register_endpoints",
    "register_routes",
    "reset_cancellation_registry",
    "sweep_cancellation_registry",
)


async def get_cancellation_registry_snapshot(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    coordinator = api_context.dependencies.cancellation_coordinator
    snapshot_value = await coordinator.get_snapshot()
    snapshot = snapshot_value if isinstance(snapshot_value, dict) else {}
    active_counts_value = snapshot.get("active_cancellation_counts")
    active_counts = active_counts_value if isinstance(active_counts_value, dict) else {}
    log_audit_event(
        request,
        "VIEW_CANCELLATION_REGISTRY",
        "cancellation_registry",
        {
            "active_cancellation_count": len(active_counts),
            "cancelled_cancellation_count": snapshot.get("cancelled_cancellation_count", 0),
            "total_active_tokens": snapshot.get("total_active_tokens", 0),
        },
    )
    return JSONResponse(content=snapshot)


async def reset_cancellation_registry(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    coordinator = api_context.dependencies.cancellation_coordinator
    previous = await coordinator.get_snapshot()
    if not isinstance(previous, dict):
        previous = {}
    await coordinator.reset_all()
    details = {
        "previous_active_tokens": previous.get("total_active_tokens", 0),
        "previous_cancelled_cancellation_count": previous.get("cancelled_cancellation_count", 0),
    }
    log_audit_event(request, "RESET_CANCELLATION_REGISTRY", "cancellation_registry", details)
    return JSONResponse(content={"message": "Cancellation registry has been reset.", **details})


async def sweep_cancellation_registry(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    coordinator = api_context.dependencies.cancellation_coordinator
    result_value = await coordinator.sweep()
    result = {
        "removed_tokens": result_value.removed_tokens,
        "cancellations_cleared": result_value.cleared_scopes,
        "remaining_cancellations": result_value.remaining_scopes,
    }
    log_audit_event(request, "SWEEP_CANCELLATION_REGISTRY", "cancellation_registry", result)
    return JSONResponse(content=result)


async def cancel_all_tasks(
    request: Request,
    payload: CancelAllTasksPayload,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    audit_details: dict[str, JSONValue] = {
        "reason": payload.reason,
        "include_internal": payload.include_internal,
    }
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        CancelAllTasksCommand,
        "final",
        "CANCEL_ALL_TASKS",
        "cancellation_registry",
        audit_details,
        {
            "reason": payload.reason,
            "include_internal": payload.include_internal,
        },
    )


def register_endpoints(router: APIRouter) -> None:
    cancellation_admin_deps = require_action_dependencies(AccessAction.REQUEST_CANCELLATION_ADMIN)
    restart_cancellation_admin_deps = tuple(
        restart_protected_dependencies(AccessAction.REQUEST_CANCELLATION_ADMIN),
    )
    router.get(
        "/cancellations",
        dependencies=cancellation_admin_deps,
    )(get_cancellation_registry_snapshot)
    router.post(
        "/cancellations/reset",
        status_code=202,
        dependencies=restart_cancellation_admin_deps,
    )(reset_cancellation_registry)
    router.post(
        "/cancellations/sweep",
        dependencies=restart_cancellation_admin_deps,
    )(sweep_cancellation_registry)
    router.post(
        "/cancel-all",
        status_code=202,
        dependencies=restart_cancellation_admin_deps,
    )(cancel_all_tasks)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.tasks)
