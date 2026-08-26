"""SoAI - Automation occurrence and run query routes [backend/features/api/routes/automations/window_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse

from core.automation.automation_constants import (
    AUTOMATION_OCCURRENCES_MAX_ITEMS,
    AUTOMATION_RUNS_DEFAULT_LIMIT,
)
from core.errors.exceptions import NotFoundError, ValidationError
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.automations.query_validation import (
    require_automation_occurrences_pagination,
    require_automation_runs_pagination,
    require_automation_window_bounds,
)
from features.api.routes.automations.run_side_effects import (
    process_occurrence_deletion_run_side_effects,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_bad_request, raise_not_found
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.automations import AutomationOccurrencesDelete
from features.automation.occurrence_window_pagination import paginate_occurrence_window

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.automations.get(
        "/occurrences",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def get_automation_occurrences(
        request: Request,
        from_utc_ms: int = Query(...),
        to_utc_ms: int = Query(...),
        limit: int = Query(default=AUTOMATION_OCCURRENCES_MAX_ITEMS),
        offset: int = Query(default=0),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        require_automation_window_bounds(request, from_utc_ms=from_utc_ms, to_utc_ms=to_utc_ms)
        require_automation_occurrences_pagination(request, limit=limit, offset=offset)
        automations_task = (
            api_context.dependencies.database_automations.list_enabled_automation_window_sources(
                current_user["id"],
            )
        )
        runs_task = api_context.dependencies.database_automation_runs.list_runs_for_window(
            current_user["id"],
            from_utc_ms=from_utc_ms,
            to_utc_ms=to_utc_ms,
        )
        deleted_keys_task = api_context.dependencies.database_automation_occurrence_deletions.list_occurrence_deletions_for_window(
            current_user["id"],
            from_utc_ms=from_utc_ms,
            to_utc_ms=to_utc_ms,
        )
        automations, runs, deleted_keys = await asyncio.gather(
            automations_task,
            runs_task,
            deleted_keys_task,
            return_exceptions=False,
        )
        try:
            page, has_more, next_offset = paginate_occurrence_window(
                automations=automations,
                runs=runs,
                deleted_keys=deleted_keys,
                from_utc_ms=from_utc_ms,
                to_utc_ms=to_utc_ms,
                limit=limit,
                offset=offset,
            )
        except ValidationError as exception:
            raise_bad_request(
                request,
                str(exception),
            )
        return JSONResponse(
            content={
                "occurrences": page,
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
                "next_offset": next_offset,
            },
        )

    @routers.automations.post(
        "/occurrences/delete",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def delete_automation_occurrences(
        request: Request,
        payload: AutomationOccurrencesDelete,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        now_ms = epoch_ms()
        try:
            result = await api_context.dependencies.database_automation_occurrence_deletions.delete_occurrences(
                current_user["id"],
                occurrences=[
                    (item.automation_id, item.scheduled_at_ms) for item in payload.occurrences
                ],
                deleted_at_ms=now_ms,
            )
        except NotFoundError as exception:
            raise_not_found(request, str(exception))
        except ValidationError as exception:
            raise_bad_request(
                request,
                str(exception),
            )
        await process_occurrence_deletion_run_side_effects(request, api_context, result)
        return JSONResponse(content=result)

    @routers.automations.get(
        "/runs/active",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def list_active_automation_runs(
        _request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        records = await api_context.dependencies.database_automation_runs.list_active_runs(
            current_user["id"],
        )
        return JSONResponse(content=records)

    @routers.automations.get(
        "/runs",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def list_automation_runs(
        request: Request,
        from_utc_ms: int = Query(...),
        to_utc_ms: int = Query(...),
        automation_id: str | None = Query(default=None),
        limit: int = Query(default=AUTOMATION_RUNS_DEFAULT_LIMIT),
        offset: int = Query(default=0),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        require_automation_window_bounds(request, from_utc_ms=from_utc_ms, to_utc_ms=to_utc_ms)
        require_automation_runs_pagination(request, limit=limit, offset=offset)
        records = await api_context.dependencies.database_automation_runs.list_runs(
            current_user["id"],
            from_utc_ms=from_utc_ms,
            to_utc_ms=to_utc_ms,
            automation_id=automation_id,
            limit=limit,
            offset=offset,
        )
        return JSONResponse(content=records)

    @routers.automations.get(
        "/runs/{run_id}",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def get_automation_run(
        request: Request,
        run_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        record = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_automation_runs.get_run(run_id, current_user["id"]),
            message="Automation run not found.",
        )
        return JSONResponse(content=record)
