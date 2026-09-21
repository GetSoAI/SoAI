"""SoAI - WebUI self-service user routes [backend/features/api/routes/webui/users_self_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.errors.exceptions import NotFoundError, StateError, ValidationError
from core.media.tesseract_data import tesseract_model_available
from core.media.tesseract_languages import get_tesseract_catalog
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.routes.webui.user_identity_validation import require_username
from features.api.routes.webui.user_password_changes import change_webui_user_password
from features.api.routes.webui.users_common import serialize_user_response
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_not_found,
)
from features.api.runtime.user_coercion import current_user_to_json_dict
from features.api.schemas.users import UserPasswordUpdate, UserPreferencesUpdate

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    router = routers.webui

    @router.get("/users/me")
    async def read_users_me(
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return JSONResponse(
            content=serialize_user_response(
                api_context,
                current_user_to_json_dict(current_user),
            ),
        )

    @router.patch(
        "/users/me/password",
        status_code=200,
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def change_current_user_password(
        request: Request,
        payload: UserPasswordUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        result = await change_webui_user_password(
            request=request,
            api_context=api_context,
            current_user=current_user,
            payload=payload,
            target_user_id=None,
        )
        return result.response

    @router.get("/ocr/languages")
    async def get_ocr_languages(
        _current_user: CurrentUser = Depends(get_current_user),
    ) -> Response:
        data_directory = os.environ.get("TESSDATA_PREFIX", "")
        payload: JSONDict = {
            "languages": [
                {
                    "code": entry.code,
                    "name": entry.name,
                    "native_name": entry.native_name,
                    "flag": entry.flag,
                    "ui_locale": entry.ui_locale,
                    "available": tesseract_model_available(data_directory, entry.code),
                }
                for entry in get_tesseract_catalog().languages
            ]
        }
        return JSONResponse(content=payload)

    @router.get("/users/me/preferences")
    async def get_my_preferences(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            preferences = await api_context.dependencies.webui_manager.get_user_preferences(
                current_user["id"],
            )
            return JSONResponse(content=preferences)
        except NotFoundError:
            raise_not_found(request, "Current user not found.")

    @router.patch("/users/me/preferences")
    async def update_my_preferences(
        request: Request,
        payload: UserPreferencesUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        settings = payload.preferences.get("settings")
        if isinstance(settings, dict) and "ocr_language" in settings:
            if payload.intended_user_id != current_user["id"]:
                raise ValidationError(
                    "OCR preference mutation requires the authenticated intended user."
                )
        username = require_username(request, current_user)
        log_audit_event(request, "UPDATE_PREFERENCES", f"user:{username}")
        try:
            preferences = await api_context.dependencies.webui_manager.update_user_preferences(
                current_user["id"],
                payload.preferences,
            )
            return JSONResponse(content=preferences)
        except NotFoundError:
            raise_not_found(request, "Current user not found.")
        raise StateError("Preference retrieval did not raise as expected.")

    @router.post("/users/me/preferences/reset")
    async def reset_my_preferences(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> dict[str, str]:
        username = require_username(request, current_user)
        log_audit_event(request, "RESET_PREFERENCES", f"user:{username}")
        try:
            await api_context.dependencies.webui_manager.reset_user_preferences(current_user["id"])
            return {"message": "Preferences have been reset to defaults."}
        except NotFoundError:
            raise_not_found(request, "Current user not found.")
        raise StateError("Preference reset did not raise as expected.")

    @router.post("/users/me/tool-approval-permissions/reset")
    async def reset_my_tool_approval_permissions(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> dict[str, str]:
        username = require_username(request, current_user)
        log_audit_event(request, "RESET_TOOL_APPROVAL_PERMISSIONS", f"user:{username}")
        preferences = await api_context.dependencies.database_users.clear_tool_approval_permissions(
            current_user["id"]
        )
        if preferences is None:
            raise_not_found(request, "Current user not found.")
        return {"message": "Tool approval permissions have been reset."}

    @router.post("/users/me/password-vault/reset")
    async def reset_my_password_vault(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> dict[str, int | str]:
        username = require_username(request, current_user)
        log_audit_event(request, "RESET_PASSWORD_VAULT", f"user:{username}")
        user = await api_context.dependencies.database_users.get_human_user_by_id(
            current_user["id"]
        )
        if user is None:
            raise_not_found(request, "Current user not found.")
        deleted_credentials = (
            await api_context.dependencies.database_password_vault.delete_all_credentials(
                current_user["id"],
            )
        )
        cleared_secret_handles = api_context.dependencies.secret_handle_store.forget_all_for_user(
            current_user["id"],
        )
        return {
            "message": "Password vault has been reset.",
            "deleted_credentials": deleted_credentials,
            "cleared_secret_handles": cleared_secret_handles,
        }
