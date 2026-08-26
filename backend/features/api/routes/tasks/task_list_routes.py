"""SoAI - Task listing routes [backend/features/api/routes/tasks/task_list_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request

from core.state.access import AccessAction
from core.tasks.api_models import TaskQueryResponse
from core.tasks.api_queries import query_active_tasks_for_user, task_to_response
from core.tasks.list_limits import resolve_task_list_limits
from features.api.routes.tasks.task_query_models import TaskListResponse
from features.api.routes.tasks.task_visibility_rules import (
    parse_task_type_filter,
    require_task_visibility,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request, raise_not_found

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.tasks.get(
        "/active",
        response_model=TaskListResponse,
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def list_active_tasks(
        request: Request,
        task_type: str | None = Query(None, description="Filter by task type"),
        limit: int | None = Query(
            None,
            ge=1,
            le=100000,
            description="Maximum number of tasks to return",
        ),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> TaskListResponse:
        max_limit, default_limit, _ = resolve_task_list_limits(api_context.dependencies.config)
        effective_limit = default_limit if limit is None else int(limit)
        if effective_limit > max_limit:
            raise_invalid_request(
                request,
                f"limit exceeds configured SYSTEM.TASKS.TASK_LIST_MAX_LIMIT ({max_limit}).",
            )
        registry_queries = api_context.dependencies.task_registry_queries
        task_type_filter = parse_task_type_filter(
            request,
            task_type,
            registry_queries.task_catalog,
        )
        all_tasks, total_count = await query_active_tasks_for_user(
            user_id=current_user["id"],
            is_admin=current_user["is_admin"],
            task_type_filter=task_type_filter,
            effective_limit=effective_limit,
            registry=registry_queries,
        )
        task_responses = [task_to_response(task) for task in all_tasks]
        api_context.dependencies.metrics_manager.increment_counter("api", "tasks", "list_active")
        return TaskListResponse(
            tasks=task_responses,
            total_count=total_count,
            limit=effective_limit,
            offset=0,
        )

    @routers.tasks.get(
        "",
        response_model=TaskListResponse,
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def list_tasks(
        request: Request,
        task_type: str | None = Query(
            None,
            description=(
                "Filter by task type "
                "(chat_completion, mcp_tool_call, mcp_sampling, mcp_elicitation)"
            ),
        ),
        active_only: bool = Query(False, description="Only return active (non-terminal) tasks"),
        limit: int = Query(100, ge=1, le=100000, description="Maximum number of tasks to return"),
        offset: int = Query(0, ge=0, description="Number of tasks to skip"),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> TaskListResponse:
        max_limit, _, max_offset = resolve_task_list_limits(api_context.dependencies.config)
        if int(limit) > max_limit:
            raise_invalid_request(
                request,
                f"limit exceeds configured SYSTEM.TASKS.TASK_LIST_MAX_LIMIT ({max_limit}).",
            )
        if int(offset) > max_offset:
            raise_invalid_request(
                request,
                f"offset exceeds configured SYSTEM.TASKS.TASK_LIST_MAX_OFFSET ({max_offset}).",
            )
        user_id = current_user["id"]
        registry_queries = api_context.dependencies.task_registry_queries
        task_type_filter = parse_task_type_filter(
            request,
            task_type,
            registry_queries.task_catalog,
        )
        all_tasks, total_count = await registry_queries.query_visible_to_user_with_count(
            user_id=user_id,
            include_system=current_user["is_admin"],
            task_type=task_type_filter,
            active_only=active_only,
            limit=int(limit),
            offset=int(offset),
        )
        task_responses = [task_to_response(task) for task in all_tasks]
        api_context.dependencies.metrics_manager.increment_counter("api", "tasks", "list")
        return TaskListResponse(
            tasks=task_responses,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    @routers.tasks.get(
        "/{task_id}",
        response_model=TaskQueryResponse,
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def get_task(
        request: Request,
        task_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> TaskQueryResponse:
        registry = api_context.dependencies.task_registry
        task = await registry.get(task_id)
        if not task:
            raise_not_found(request, f"Task not found: {task_id}")
        require_task_visibility(request, task, current_user)
        api_context.dependencies.metrics_manager.increment_counter("api", "tasks", "get")
        return task_to_response(task)
