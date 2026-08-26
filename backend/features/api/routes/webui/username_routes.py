"""SoAI - WebUI username mutation and status routes [backend/features/api/routes/webui/username_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.errors.exceptions import ApiError, ConflictError
from core.mutations.identifiers import require_mutation_request_id
from core.state.access import AccessAction
from core.users.identity_mutation_records import (
    IdentityMutationBinding,
)
from core.users.user_id import require_strict_user_id
from features.api.routes.webui.identity_mutation_throttling import (
    enforce_identity_mutation_attempt_limit,
)
from features.api.routes.webui.user_mutation_responses import (
    serialize_identity_mutation_record,
)
from features.api.routes.webui.username_rename_orchestration import rename_username
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.users import UserMutationStatusPayload, UsernameRenamePayload


async def _rename_response(
    request: Request,
    api_context: ApiContext,
    actor_user_id: int,
    target_user_id: int,
    payload: UsernameRenamePayload,
) -> Response:
    outcome = await rename_username(
        request=request,
        api_context=api_context,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        payload=payload,
    )
    return outcome.response


def register_routes(routers: ApiRouters) -> None:
    router = routers.webui

    @router.patch(
        "/users/me/username",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def rename_current_username(
        request: Request,
        payload: UsernameRenamePayload,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        actor_user_id = require_strict_user_id(current_user.get("id"))
        return await _rename_response(
            request,
            api_context,
            actor_user_id,
            actor_user_id,
            payload,
        )

    @router.patch(
        "/users/{user_id}/username",
        dependencies=require_action_dependencies(AccessAction.USER_ADMIN),
    )
    async def rename_username_by_admin(
        request: Request,
        user_id: int,
        payload: UsernameRenamePayload,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await _rename_response(
            request,
            api_context,
            require_strict_user_id(current_user.get("id")),
            require_strict_user_id(user_id),
            payload,
        )

    @router.post(
        "/users/mutations/{operation_id}/status",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def user_mutation_status(
        request: Request,
        operation_id: str,
        payload: UserMutationStatusPayload,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        canonical_operation_id = require_mutation_request_id(operation_id)
        actor_user_id = require_strict_user_id(current_user.get("id"))
        await enforce_identity_mutation_attempt_limit(
            request,
            api_context,
            actor_or_source=str(actor_user_id),
        )
        actor = await api_context.dependencies.database_users.get_human_user_by_id(actor_user_id)
        if actor is None:
            raise ApiError(
                "User mutation was not found.",
                code="user_mutation_not_found",
                http_status=404,
            )
        proposed_target_id = payload.target_user_id
        if proposed_target_id is not None and proposed_target_id != actor_user_id:
            if actor.get("is_admin") is not True:
                raise ApiError(
                    "User mutation was not found.",
                    code="user_mutation_not_found",
                    http_status=404,
                )
        if payload.finalize_absence is True:
            if payload.operation_type is None:
                raise ApiError(
                    "Invalid mutation binding.", code="invalid_request_error", http_status=422
                )
            if payload.target_user_id is None:
                raise ApiError(
                    "Invalid mutation binding.", code="invalid_request_error", http_status=422
                )
            binding = IdentityMutationBinding(
                actor_user_id=actor_user_id,
                operation_id=canonical_operation_id,
                operation_type=payload.operation_type,
                target_user_id=payload.target_user_id,
                requested_username=payload.requested_username,
            )
            try:
                record = await api_context.dependencies.database_user_mutations.finalize_absence(
                    binding
                )
            except ConflictError as exception:
                raise ApiError(
                    "Mutation operation ID is bound to different input.",
                    code="operation_id_conflict",
                    http_status=409,
                    cause=exception,
                ) from exception
            if record is None:
                raise ApiError(
                    "User mutation was not found.",
                    code="user_mutation_not_found",
                    http_status=404,
                )
        else:
            record = await api_context.dependencies.database_user_mutations.read_by_actor_operation(
                actor_user_id,
                canonical_operation_id,
            )
            if record is None:
                raise ApiError(
                    "User mutation was not found.",
                    code="user_mutation_not_found",
                    http_status=404,
                )
        if record.binding.target_user_id != actor_user_id and actor.get("is_admin") is not True:
            raise ApiError(
                "User mutation was not found.",
                code="user_mutation_not_found",
                http_status=404,
            )
        response = JSONResponse(content=serialize_identity_mutation_record(record))
        response.headers["Cache-Control"] = "no-store"
        return response


__all__ = ("register_routes",)
