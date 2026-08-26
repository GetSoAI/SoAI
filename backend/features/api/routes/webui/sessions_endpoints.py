"""SoAI - WebUI device-session endpoints [backend/features/api/routes/webui/sessions_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
import uuid

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.auth.jwt_tokens import require_request_session_jti
from core.auth.webui_sessions import WEBUI_DEVICE_LABEL_MAX_LENGTH
from core.errors.exceptions import ValidationError
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.users.user_id import require_strict_user_id
from core.validation.strings import require_bounded_trimmed_text
from features.api.routes.webui.user_identity_validation import require_username
from features.api.routes.webui.webui_auth_resource_locking import (
    lock_webui_auth_resources,
    session_mutation_resource,
    username_auth_resource,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_not_found
from features.api.schemas.users import WebuiAndroidSessionRename

__all__ = ("register_routes",)


def _canonical_device_id(value: str) -> str:
    try:
        return str(uuid.UUID(value.strip()))
    except ValueError as exception:
        raise ValidationError("Device id must be a UUID.") from exception


def register_routes(routers: ApiRouters) -> None:
    router = routers.webui

    @router.get("/sessions")
    async def list_sessions(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        database_tokens = api_context.dependencies.webui_manager.database_tokens
        sessions = await database_tokens.list_active_sessions(
            user_id=require_strict_user_id(current_user["id"]),
            current_jti=require_request_session_jti(request),
        )
        return JSONResponse(content={"sessions": sessions})

    @router.delete("/sessions")
    async def revoke_all_sessions(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        user_id = require_strict_user_id(current_user["id"])
        username = require_username(request, current_user)
        current_jti = require_request_session_jti(request)
        database_tokens = api_context.dependencies.webui_manager.database_tokens
        async with lock_webui_auth_resources(
            api_context.dependencies.login_attempt_locks,
            (
                username_auth_resource(username),
                session_mutation_resource(current_jti),
            ),
        ):
            revocation = await database_tokens.revoke_all_user_sessions(
                user_id=user_id,
                deadline_monotonic=time.monotonic() + INTERACTIVE_TIMEOUT_SEC,
            )
        log_audit_event(
            request,
            "REVOKE_ALL_WEBUI_SESSIONS",
            f"user:{revocation.username}",
            {
                "revoked_count": len(revocation.revoked_jtis),
                "session_jtis": list(revocation.revoked_jtis),
            },
        )
        return JSONResponse(content={"message": "All sessions revoked successfully."})

    @router.delete("/sessions/{jti}")
    async def revoke_session(
        request: Request,
        jti: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        user_id = require_strict_user_id(current_user["id"])
        database_tokens = api_context.dependencies.webui_manager.database_tokens
        async with lock_webui_auth_resources(
            api_context.dependencies.login_attempt_locks,
            (session_mutation_resource(jti),),
        ):
            revocation = await database_tokens.revoke_owned_session_lineage(
                user_id=user_id,
                source_jti=jti,
                deadline_monotonic=time.monotonic() + INTERACTIVE_TIMEOUT_SEC,
            )
        if revocation is None or not revocation.revoked_jtis:
            raise_not_found(request, "Active session not found.")
        log_audit_event(
            request,
            "REVOKE_WEBUI_SESSION",
            f"session:{jti}",
            {"session_jtis": list(revocation.revoked_jtis)},
        )
        return JSONResponse(content={"message": "Session revoked successfully."})

    @router.patch("/sessions/current")
    async def rename_current_android_session(
        request: Request,
        payload: WebuiAndroidSessionRename,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        device_label = require_bounded_trimmed_text(
            payload.device_label,
            type_message="Device label must be a string.",
            empty_message="Device label must not be empty.",
            max_length=WEBUI_DEVICE_LABEL_MAX_LENGTH,
            max_length_message="Device label must be 80 characters or fewer.",
        )
        database_tokens = api_context.dependencies.webui_manager.database_tokens
        renamed = await database_tokens.rename_android_session(
            user_id=require_strict_user_id(current_user["id"]),
            jti=require_request_session_jti(request),
            device_id=_canonical_device_id(payload.device_id),
            device_label=device_label,
        )
        if not renamed:
            raise_not_found(request, "Current Android session not found.")
        log_audit_event(request, "RENAME_WEBUI_SESSION", "session:current")
        return JSONResponse(content={"message": "Device name updated successfully."})
