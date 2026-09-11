"""SoAI - Automation CRUD and run-now routes [backend/features/api/routes/automations/definition_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from core.automation.automation_definition_updates import update_automation_definition
from core.automation.automation_model_reference import (
    build_automation_model_validation_payload,
    should_validate_automation_update_model_reference,
    validate_automation_payload_model_reference,
)
from core.automation.automation_run_task_lifecycle import (
    ensure_automation_run_owner_task_attached,
)
from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.errors.exceptions import ConflictError, ValidationError
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from core.workspaces.model_settings_workspace_path import (
    normalize_payload_model_settings_workspace_path,
)
from core.workspaces.user_workspace_path import (
    require_authenticated_user_workspace_path,
    resolve_user_record_workspace_access,
)
from features.api.routes.automations.query_validation import (
    require_automation_list_pagination,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_invalid_request, raise_not_found
from features.api.runtime.request_payloads import (
    read_required_json_dict_payload_or_raise,
)
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.user_coercion import current_user_to_json_dict
from features.api.runtime.webui_records import webui_fetch_or_404

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "create_automation",
    "delete_automation",
    "get_automation",
    "list_automations",
    "register_endpoints",
    "register_routes",
    "run_automation_now",
    "update_automation",
)

AUTOMATION_LIST_DEFAULT_LIMIT = 100
AUTOMATION_LIST_MAX_LIMIT = 1000


async def _validate_automation_payload_model(
    request: Request,
    api_context: ApiContext,
    payload: JSONDict,
) -> None:
    try:
        await validate_automation_payload_model_reference(
            payload,
            now_ms=epoch_ms(),
            disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
                api_context.dependencies.config,
            ),
            model_resolution_service=api_context.dependencies.model_resolution_service,
            model_information_service=api_context.dependencies.model_information_service,
            model_virtual_model_service=api_context.dependencies.model_virtual_model_service,
        )
    except ValidationError as exception:
        raise_invalid_request(
            request,
            str(exception),
            error_type=str(exception.code),
            extra=exception.details,
        )


async def list_automations(
    request: Request,
    limit: int = Query(default=AUTOMATION_LIST_DEFAULT_LIMIT),
    offset: int = Query(default=0),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    require_automation_list_pagination(
        request,
        limit=limit,
        offset=offset,
        max_limit=AUTOMATION_LIST_MAX_LIMIT,
    )
    records, has_more = await api_context.dependencies.database_automations.list_automations(
        current_user["id"],
        limit=limit,
        offset=offset,
    )
    next_offset = offset + len(records) if has_more else None
    return JSONResponse(
        content={
            "automations": records,
            "has_more": has_more,
            "next_offset": next_offset,
            "limit": limit,
            "offset": offset,
        },
    )


async def create_automation(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    payload = await read_required_json_dict_payload_or_raise(
        request,
        invalid_message="Request body must be a JSON object.",
        server_error_message="Automation payload is invalid.",
    )
    resolve_user_record_workspace_access(
        api_context.dependencies.files,
        current_user_to_json_dict(current_user),
    )
    normalized_payload = normalize_payload_model_settings_workspace_path(
        files=api_context.dependencies.files,
        payload=payload,
        user_workspace_path=require_authenticated_user_workspace_path(
            current_user.get("workspace_path"),
        ),
    )
    await _validate_automation_payload_model(request, api_context, normalized_payload)
    created = await api_context.dependencies.database_automations.create_automation(
        current_user["id"],
        normalized_payload,
    )
    return JSONResponse(status_code=201, content=created)


async def get_automation(
    request: Request,
    automation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    record = await webui_fetch_or_404(
        request,
        api_context.dependencies.database_automations.get_automation(
            automation_id,
            current_user["id"],
        ),
        message="Automation not found.",
    )
    return JSONResponse(content=record)


async def update_automation(
    request: Request,
    automation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    patch_payload = await read_required_json_dict_payload_or_raise(
        request,
        invalid_message="Request body must be a JSON object.",
        server_error_message="Automation payload is invalid.",
    )
    resolve_user_record_workspace_access(
        api_context.dependencies.files,
        current_user_to_json_dict(current_user),
    )
    normalized_patch_payload = normalize_payload_model_settings_workspace_path(
        files=api_context.dependencies.files,
        payload=patch_payload,
        user_workspace_path=require_authenticated_user_workspace_path(
            current_user.get("workspace_path"),
        ),
    )
    if should_validate_automation_update_model_reference(normalized_patch_payload):
        current_record = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_automations.get_automation(
                automation_id,
                current_user["id"],
            ),
            message="Automation not found.",
        )
        validation_payload = build_automation_model_validation_payload(
            current_record,
            normalized_patch_payload,
        )
        await _validate_automation_payload_model(request, api_context, validation_payload)
    result = await update_automation_definition(
        api_context.dependencies.database_automations,
        api_context.dependencies.task_registry,
        automation_id=automation_id,
        user_id=current_user["id"],
        payload=normalized_patch_payload,
        event_bus=api_context.dependencies.event_bus,
        database_chat_identity_defaults=(api_context.dependencies.database_chat_identity_defaults),
        database_chat_model_defaults=api_context.dependencies.database_chat_model_defaults,
    )
    if not isinstance(result.automation, dict):
        raise_not_found(request, "Automation not found.")
    return JSONResponse(content=result.automation)


async def delete_automation(
    request: Request,
    automation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    try:
        deleted = await api_context.dependencies.database_automations.delete_automation(
            automation_id,
            current_user["id"],
        )
    except ConflictError as exception:
        raise_conflict(request, str(exception), extra=exception.details)
    if not deleted:
        raise_not_found(request, "Automation not found.")
    return create_no_content_response()


async def run_automation_now(
    request: Request,
    automation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    automation_record = await webui_fetch_or_404(
        request,
        api_context.dependencies.database_automations.get_automation(
            automation_id,
            current_user["id"],
        ),
        message="Automation not found.",
    )
    validation_payload = build_automation_model_validation_payload(automation_record, {})
    await _validate_automation_payload_model(request, api_context, validation_payload)
    try:
        run_record = await api_context.dependencies.database_automation_runs.create_run_now(
            automation_id,
            current_user["id"],
            epoch_ms(),
        )
    except ConflictError as exception:
        raise_conflict(request, str(exception), extra=exception.details)
    run_record = await ensure_automation_run_owner_task_attached(
        api_context.dependencies.database_automation_runs,
        api_context.dependencies.task_registry,
        run_record=run_record,
    )
    return JSONResponse(content=run_record)


def register_endpoints(router: APIRouter) -> None:
    auth_cookie_deps = require_action_dependencies(AccessAction.AUTH_COOKIE)
    router.get("", dependencies=auth_cookie_deps)(list_automations)
    router.post("", dependencies=auth_cookie_deps, status_code=201)(create_automation)
    router.get("/{automation_id}", dependencies=auth_cookie_deps)(get_automation)
    router.patch("/{automation_id}", dependencies=auth_cookie_deps)(update_automation)
    router.delete("/{automation_id}", dependencies=auth_cookie_deps, status_code=204)(
        delete_automation,
    )
    router.post("/{automation_id}/run-now", dependencies=auth_cookie_deps)(run_automation_now)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.automations)
