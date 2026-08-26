"""SoAI - Conversation workspace path config WebUI route registration [backend/features/api/routes/webui/conversation_workspace_path_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request

from core.errors.exceptions import ValidationError
from core.workspaces.model_settings_workspace_path import (
    apply_model_settings_workspace_path_update,
)
from core.workspaces.user_workspace_path import (
    require_authenticated_user_workspace_path,
    resolve_user_record_workspace_access,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import (
    require_conversation_access,
    resolve_conversation_access_id,
)
from features.api.runtime.conversation_model_settings import (
    update_conversation_model_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request
from features.api.runtime.user_coercion import current_user_to_json_dict
from features.api.runtime.validation import require_conversation_model_settings_payload
from features.api.schemas.conversation_workspace_path import (
    ConversationWorkspacePathConfigResponse,
    ConversationWorkspacePathConfigUpdate,
)
from features.file_explorer.conversation_workspace_path import (
    inspect_conversation_workspace_path_config,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/conversations/{conv_id}/workspace-path",
        response_model=ConversationWorkspacePathConfigResponse,
    )
    async def get_conversation_workspace_path_config(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONDict:
        resolve_user_record_workspace_access(
            api_context.dependencies.files,
            current_user_to_json_dict(current_user),
        )
        conversation_record = await require_conversation_access(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        response_payload = _inspect_config(
            conv_id=resolve_conversation_access_id(conversation_record, conv_id),
            api_context=api_context,
            model_settings=require_conversation_model_settings_payload(
                request,
                conversation_record.get("model_settings"),
            ),
            user_workspace_path=require_authenticated_user_workspace_path(
                current_user.get("workspace_path"),
            ),
        )
        return response_payload

    @routers.webui.patch(
        "/conversations/{conv_id}/workspace-path",
        response_model=ConversationWorkspacePathConfigResponse,
    )
    async def patch_conversation_workspace_path_config(
        request: Request,
        conv_id: str,
        payload: ConversationWorkspacePathConfigUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONDict:
        resolve_user_record_workspace_access(
            api_context.dependencies.files,
            current_user_to_json_dict(current_user),
        )
        initial_record = await require_conversation_access(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        resolved_conv_id = resolve_conversation_access_id(initial_record, conv_id)
        async with api_context.dependencies.conversation_agent_settings_locks.lock(
            (current_user["id"], resolved_conv_id),
        ):
            conversation_record = await require_conversation_access(
                request,
                api_context=api_context,
                conv_id=resolved_conv_id,
                user_id=current_user["id"],
            )
            settings = require_conversation_model_settings_payload(
                request,
                conversation_record.get("model_settings"),
            )
            try:
                next_settings = _build_updated_settings(
                    api_context=api_context,
                    model_settings=settings,
                    payload=payload,
                    user_workspace_path=require_authenticated_user_workspace_path(
                        current_user.get("workspace_path"),
                    ),
                )
            except ValidationError as exception:
                raise_invalid_request(request, exception.message)
            updated_record = await update_conversation_model_settings(
                request,
                api_context=api_context,
                conv_id=resolved_conv_id,
                user_id=current_user["id"],
                model_settings=next_settings,
            )
            return _inspect_config(
                conv_id=resolve_conversation_access_id(updated_record, resolved_conv_id),
                api_context=api_context,
                model_settings=require_conversation_model_settings_payload(
                    request,
                    updated_record.get("model_settings"),
                ),
                user_workspace_path=require_authenticated_user_workspace_path(
                    current_user.get("workspace_path"),
                ),
            )


def _build_updated_settings(
    *,
    api_context: ApiContext,
    model_settings: JSONDict,
    payload: ConversationWorkspacePathConfigUpdate,
    user_workspace_path: str,
) -> JSONDict:
    next_settings: JSONDict = dict(model_settings)
    updates = payload.model_dump(exclude_unset=True)
    if "workspace_path" in updates:
        next_settings = apply_model_settings_workspace_path_update(
            files=api_context.dependencies.files,
            model_settings=next_settings,
            raw_workspace_path=updates.get("workspace_path"),
            user_workspace_path=user_workspace_path,
        )
    return next_settings


def _inspect_config(
    *,
    conv_id: str,
    api_context: ApiContext,
    model_settings: JSONDict,
    user_workspace_path: str,
) -> JSONDict:
    inspection = inspect_conversation_workspace_path_config(
        files=api_context.dependencies.files,
        user_workspace_path=user_workspace_path,
        model_settings=model_settings,
        require_existing_directories=True,
    )
    return {
        "conv_id": conv_id,
        "workspace_path": inspection.workspace_path,
        "effective_workspace_path": inspection.effective_workspace_path,
        "effective_root_fingerprint": inspection.effective_root_fingerprint,
        "is_valid": inspection.is_valid,
        "validation_code": inspection.validation_code,
        "validation_message": inspection.validation_message,
    }
