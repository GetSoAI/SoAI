"""SoAI - Automation schedule preview route [backend/features/api/routes/automations/schedule_preview_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request
from fastapi.responses import JSONResponse

from core.automation.automation_schedule_preview import preview_automation_schedule
from core.errors.exceptions import ValidationError
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request

__all__ = ("preview_schedule", "register_routes")


async def preview_schedule(
    request: Request,
    start_local: str = Query(...),
    timezone: str = Query(...),
    recurrence: str = Query(...),
    enabled: bool = Query(...),
    _current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    try:
        preview = preview_automation_schedule(
            timezone_name=timezone,
            start_local=start_local,
            recurrence=recurrence,
            enabled=enabled,
            now_ms=epoch_ms(),
        )
    except ValidationError as exception:
        raise_invalid_request(
            request,
            str(exception),
            error_type=str(exception.code),
            extra=exception.details,
        )
    return JSONResponse(content=preview)


def register_routes(routers: ApiRouters) -> None:
    routers.automations.get(
        "/schedule-preview",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )(preview_schedule)
