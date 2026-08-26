"""SoAI - OpenAI API key user assignment routes [backend/features/api/routes/webui/key_assignment_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from core.auth.api_key_assignment import APIKeyAssignmentOutcome
from core.errors.exceptions import StateError
from core.state.access import AccessAction
from core.users.user_id import require_strict_user_id
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_not_found
from features.api.runtime.request_payloads import read_json_object_payload_or_raise
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.webui_records import webui_fetch_or_404

__all__ = (
    "KeyAssignmentRouteRegistrar",
    "register_routes",
)


class KeyAssignmentRouteRegistrar:

    def __init__(self, router: APIRouter) -> None:
        self.router = router

    def register(self) -> None:
        router = self.router

        @router.patch(
            "/openai-api-keys/{key_id}/assignment",
            dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
        )
        async def handle_assign_user_to_key(
            request: Request,
            key_id: str,
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            body = await read_json_object_payload_or_raise(
                request,
                invalid_json_message="Request body must be valid JSON.",
                invalid_object_message="Request body must be a JSON object.",
            )
            user_id_value = body.get("user_id")
            assigned_user_id = require_strict_user_id(user_id_value)
            database_api_keys = api_context.dependencies.webui_manager.database_api_keys
            outcome = await database_api_keys.assign_user_to_key(key_id, assigned_user_id)
            if outcome is APIKeyAssignmentOutcome.API_KEY_NOT_FOUND:
                raise_not_found(request, "API key not found.")
            if outcome is APIKeyAssignmentOutcome.USER_NOT_FOUND:
                raise_not_found(request, "User not found.")
            if outcome is APIKeyAssignmentOutcome.API_KEY_INACTIVE:
                raise_conflict(request, "Only active API keys can be assigned.")
            if outcome is not APIKeyAssignmentOutcome.ASSIGNED:
                raise StateError("API key assignment returned an invalid outcome.")
            log_audit_event(
                request,
                "ASSIGN_USER_TO_API_KEY",
                key_id,
                {
                    "assigned_user_id": assigned_user_id,
                    "assigned_by": current_user.get("username"),
                },
            )
            return JSONResponse(content={"key_id": key_id, "assigned_user_id": assigned_user_id})

        @router.delete(
            "/openai-api-keys/{key_id}/assignment",
            status_code=204,
            dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
        )
        async def handle_unassign_user_from_key(
            request: Request,
            key_id: str,
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            database_api_keys = api_context.dependencies.webui_manager.database_api_keys
            await webui_fetch_or_404(
                request,
                database_api_keys.get_key_by_id(key_id),
                message="API key not found.",
            )
            await database_api_keys.unassign_user_from_key(key_id)
            log_audit_event(
                request,
                "UNASSIGN_USER_FROM_API_KEY",
                key_id,
                {"unassigned_by": current_user.get("username")},
            )
            return create_no_content_response()


def register_routes(routers: ApiRouters) -> None:
    _registrar = KeyAssignmentRouteRegistrar(routers.webui)
    _registrar.register()
