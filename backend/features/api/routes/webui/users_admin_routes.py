"""SoAI - WebUI admin user routes [backend/features/api/routes/webui/users_admin_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, Response, status
from fastapi.responses import JSONResponse

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.state.access import AccessAction
from core.state.access_policy_overrides import get_effective_access_policy
from core.state.errors import CannotDeleteLastAdminError, CannotDemoteLastAdminError
from core.users.user_id import require_strict_user_id
from core.workspaces.user_workspace_path import (
    resolve_user_workspace_update,
)
from features.api.routes.webui.session_invalidation import publish_user_session_invalidation
from features.api.routes.webui.user_password_changes import change_webui_user_password
from features.api.routes.webui.users_common import serialize_user_response
from features.api.routes.webui.webui_auth_resource_locking import (
    lock_webui_auth_resources,
    username_auth_resource,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_conflict,
    raise_forbidden,
    raise_invalid_request,
    raise_server_error,
)
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.terminal_access_cleanup import (
    close_terminal_sessions_for_user_state_change,
    user_record_access_state,
)
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.users import (
    AdminUserCreate,
    AdminUserRoleUpdate,
    AdminUserWorkspacePathUpdate,
    UserPasswordUpdate,
)

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.users_admin_routes"
OPERATION = "api_users.create"


def register_routes(routers: ApiRouters) -> None:
    router = routers.webui

    @router.get("/users", dependencies=require_action_dependencies(AccessAction.USER_ADMIN))
    async def list_all_users(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        users = await api_context.dependencies.webui_manager.database_users.list_human_users()
        return JSONResponse(content=[serialize_user_response(api_context, user) for user in users])

    @router.post(
        "/users",
        status_code=201,
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def create_new_user(
        request: Request,
        payload: AdminUserCreate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        log_audit_event(
            request,
            "CREATE_USER",
            f"user:{payload.username}",
            {"is_admin": payload.is_admin},
        )
        try:
            webui_manager = api_context.dependencies.webui_manager
            hashed_password = await api_context.dependencies.login_password_service.hash_password(
                payload.password,
            )
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (username_auth_resource(payload.username),),
            ):
                user = await webui_manager.create_user(
                    payload.username,
                    hashed_password,
                    payload.is_admin,
                )
            return JSONResponse(
                content=serialize_user_response(
                    api_context,
                    user,
                ),
                status_code=status.HTTP_201_CREATED,
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))

    @router.patch(
        "/users/{user_id}",
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def update_user_role_by_admin(
        request: Request,
        user_id: int,
        payload: AdminUserRoleUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        webui_manager = api_context.dependencies.webui_manager
        target_user = await webui_fetch_or_404(
            request,
            webui_manager.database_users.get_human_user_by_id(user_id),
            message="User not found.",
        )
        log_audit_event(
            request,
            "UPDATE_USER_ROLE",
            f"user:{target_user['username']}",
            {"new_is_admin": payload.is_admin},
        )
        try:
            updated_user = await webui_manager.database_users.update_user_role(
                user_id,
                payload.is_admin,
            )
        except CannotDemoteLastAdminError as exception:
            raise_conflict(request, str(exception))
        if updated_user is None:
            raise_server_error(request, "Failed to update user role.")
        if target_user.get("is_admin") != updated_user.get("is_admin"):
            previous_state = user_record_access_state(target_user)
            next_state = user_record_access_state(updated_user)
            policy = await get_effective_access_policy(
                api_context.dependencies.access_policy_cache,
                api_context.dependencies.database_plugins,
            )
            closed_sessions = await close_terminal_sessions_for_user_state_change(
                api_context,
                user_id=user_id,
                previous_state=previous_state,
                next_state=next_state,
                policy=policy,
            )
            await publish_user_session_invalidation(
                api_context.dependencies.event_bus,
                user_id=user_id,
                username=str(updated_user.get("username") or ""),
                reason="role_changed",
            )
            log_audit_event(
                request,
                "CLOSE_TERMINAL_SESSIONS_AFTER_ROLE_CHANGE",
                f"user:{updated_user['username']}",
                {"closed_terminal_sessions": closed_sessions},
            )
        return JSONResponse(content=serialize_user_response(api_context, updated_user))

    @router.patch(
        "/users/{user_id}/password",
        dependencies=require_action_dependencies(
            AccessAction.USER_ADMIN,
            AccessAction.AUTH_COOKIE,
        ),
    )
    async def update_user_password_by_admin(
        request: Request,
        user_id: int,
        payload: UserPasswordUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        result = await change_webui_user_password(
            request=request,
            api_context=api_context,
            current_user=current_user,
            payload=payload,
            target_user_id=user_id,
        )
        current_user_id = require_strict_user_id(current_user["id"])
        if result.actor_changed:
            return result.response
        if user_id == current_user_id:
            raise_server_error(request, "Password change actor state is inconsistent.")
        return result.response

    @router.patch(
        "/users/{user_id}/workspace-path",
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def update_user_workspace_path_by_admin(
        request: Request,
        user_id: int,
        payload: AdminUserWorkspacePathUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        webui_manager = api_context.dependencies.webui_manager
        target_user = await webui_fetch_or_404(
            request,
            webui_manager.database_users.get_human_user_by_id(user_id),
            message="User not found.",
        )
        try:
            default_workspace_path = target_user.get("default_workspace_path")
            if not isinstance(default_workspace_path, str):
                raise StateError("User record is missing default_workspace_path.")
            resolved_update = resolve_user_workspace_update(
                api_context.dependencies.files,
                default_workspace_path=default_workspace_path,
                requested_value=payload.workspace_path,
                require_existing_directory=True,
            )
        except ValidationError as exception:
            raise_invalid_request(request, exception.message)
        except StateError as exception:
            raise_server_error(request, exception.message)
        updated_user = await webui_manager.database_users.update_user_workspace_path(
            user_id,
            resolved_update.workspace_path,
            resolved_update.workspace_real_path,
        )
        if updated_user is None:
            raise_server_error(request, "Failed to update user workspace path.")
        log_audit_event(
            request,
            "UPDATE_USER_WORKSPACE_PATH",
            f"user:{target_user['username']}",
            {"workspace_path": resolved_update.workspace_path, "via": "rest"},
        )
        return JSONResponse(content=serialize_user_response(api_context, updated_user))

    @router.delete(
        "/users/{user_id}",
        status_code=204,
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def delete_user_by_admin(
        request: Request,
        user_id: int,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        webui_manager = api_context.dependencies.webui_manager
        target_user = await webui_manager.database_users.get_human_user_by_id(user_id)
        if not target_user:
            return create_no_content_response()
        if target_user["id"] == current_user["id"]:
            raise_forbidden(request, "Administrators cannot delete themselves.")
        log_audit_event(request, "DELETE_USER", f"user:{target_user['username']}")
        try:
            await webui_manager.delete_user(user_id)
        except CannotDeleteLastAdminError as exception:
            raise_conflict(request, str(exception))
        await publish_user_session_invalidation(
            api_context.dependencies.event_bus,
            user_id=user_id,
            username=str(target_user.get("username") or ""),
            reason="user_deleted",
        )
        return create_no_content_response()
