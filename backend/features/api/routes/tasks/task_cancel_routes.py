"""SoAI - Task cancellation routes [backend/features/api/routes/tasks/task_cancel_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.tasks.identifiers import normalize_optional_task_id
from core.tasks.task_cancellation import cancel
from features.api.middleware.acl_enforcement import require_any_actions
from features.api.routes.tasks.task_query_models import TaskCancelRequest
from features.api.routes.tasks.task_visibility_rules import require_task_visibility
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_bad_request,
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.runtime.restart import check_restart_status

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.task_cancel_routes"
OPERATION = "api_tasks.cancel_task"


def register_routes(routers: ApiRouters) -> None:
    @routers.tasks.post(
        "/{task_id}/cancel",
        status_code=202,
        dependencies=(
            Depends(check_restart_status),
            Depends(
                require_any_actions(
                    AccessAction.AUTH_COOKIE,
                    AccessAction.REQUEST_CANCELLATION_ADMIN,
                )
            ),
        ),
    )
    async def cancel_task(
        request: Request,
        task_id: str,
        payload: TaskCancelRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        logger = get_logger(LOGGER_NAME)
        registry = api_context.dependencies.task_registry
        normalized_task_id = normalize_optional_task_id(task_id)
        if normalized_task_id is None:
            raise_invalid_request(request, "task_id must be a non-empty string")
        task_id = normalized_task_id
        task = await registry.get(task_id)
        if not task:
            raise_not_found(request, f"Task not found: {task_id}")
        require_task_visibility(request, task, current_user)
        if task.status.is_terminal():
            raise_bad_request(
                request,
                f"Task already in terminal state: {task.status.value}",
                error_type="invalid_state",
            )
        try:
            updated_task = await cancel(
                registry,
                task_id,
                reason=payload.reason,
                context=request.state.context,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to cancel task",
                operation=OPERATION,
            )
            raise_server_error(request, "Failed to cancel task")
        if updated_task is None:
            updated_task = await registry.get(task_id, force_refresh=True)
            if updated_task is None:
                raise_not_found(request, f"Task not found: {task_id}")
        log_audit_event(request, "CANCEL_TASK", task_id)
        api_context.dependencies.metrics_manager.increment_counter("api", "tasks", "cancel")
        return JSONResponse(
            content={
                "success": True,
                "task_id": task_id,
                "cancellation_requested": True,
                "cancellation_requested_at_ms": updated_task.cancellation_requested_at_ms,
                "status": updated_task.status.value,
            },
        )
