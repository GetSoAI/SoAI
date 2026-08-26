"""SoAI - Conversation settings update flow [backend/features/api/routes/webui/conversation_settings_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.conversations.conversation_mcp_extensions import (
    CONVERSATION_MCP_EXTENSION_FIELDS,
)
from core.conversations.settings_authority import (
    resolve_conversation_settings_authority,
)
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from core.mcp.tool_catalog_scope import (
    INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE,
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
)
from core.model_settings.normalization import (
    extract_agent_mode,
    merge_model_settings,
    normalize_chat_execution_settings,
)
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from core.workspaces.model_settings_workspace_path import (
    apply_model_settings_workspace_path_update,
)
from core.workspaces.user_workspace_path import (
    require_authenticated_user_workspace_path,
    resolve_user_record_workspace_access,
)
from features.api.routes.webui.conversation_agent_mode_events import (
    publish_agent_mode_changed_event,
)
from features.api.routes.webui.conversation_agent_settings_update_guard import (
    require_agent_settings_update_allowed,
)
from features.api.runtime.conversation_access import resolve_conversation_access_id
from features.api.runtime.conversation_mcp_catalog_state import (
    load_conversation_mcp_catalog_state,
)
from features.api.runtime.conversation_mcp_state_merge import (
    merge_conversation_mcp_config_update,
)
from features.api.runtime.conversation_model_settings import (
    update_conversation_model_settings,
)
from features.api.runtime.conversation_settings_mutation import (
    require_conversation_settings_mutable,
)
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_server_error,
)
from features.api.runtime.mcp_enabled_mode_validation import (
    validate_enabled_tools_for_agent_mode,
)
from features.api.runtime.mcp_server_configs_validation import load_mcp_server_ids
from features.api.runtime.model_settings_mcp import (
    normalize_model_settings_mcp_for_owner,
)
from features.api.runtime.user_coercion import current_user_to_json_dict
from features.api.runtime.validation import require_conversation_model_settings_payload
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.mcp_config import ConversationMCPConfigUpdate

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser
    from features.api.schemas.conversations import ConversationSettingsUpdate

LOGGER_NAME = "SoAI.features.api.conversation_settings_update"

__all__ = ("update_conversation_settings_record",)


async def update_conversation_settings_record(
    *,
    request: Request,
    conv_id: str,
    payload: ConversationSettingsUpdate,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> tuple[JSONDict, str, str]:
    api_context.dependencies.metrics_manager.increment_counter(
        "api",
        "webui",
        "conversation_settings_updated",
    )
    existing_conversation = await webui_fetch_or_404(
        request,
        api_context.dependencies.database_conversations.get_conversation(
            conv_id,
            current_user["id"],
        ),
        message="Conversation not found.",
    )
    resolved_conv_id = resolve_conversation_access_id(existing_conversation, conv_id)
    async with api_context.dependencies.conversation_agent_settings_locks.lock(
        (current_user["id"], resolved_conv_id),
    ):
        current_conversation = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_conversations.get_conversation(
                resolved_conv_id,
                current_user["id"],
            ),
            message="Conversation not found.",
        )
        settings_authority = resolve_conversation_settings_authority(current_conversation)
        require_conversation_settings_mutable(request, settings_authority)
        existing_settings = require_conversation_model_settings_payload(
            request,
            current_conversation.get("model_settings"),
        )
        try:
            previous_mode = extract_agent_mode(existing_settings, strict=False)
        except ValidationError as error:
            raise StateError(error.message) from error
        merged_settings = merge_model_settings(
            existing_settings, dict(payload.model_settings or {})
        )
        model_settings_patch = payload.model_settings
        if isinstance(model_settings_patch, dict) and "workspace_path" in model_settings_patch:
            try:
                resolve_user_record_workspace_access(
                    api_context.dependencies.files,
                    current_user_to_json_dict(current_user),
                )
                merged_settings = apply_model_settings_workspace_path_update(
                    files=api_context.dependencies.files,
                    model_settings=merged_settings,
                    raw_workspace_path=model_settings_patch.get("workspace_path"),
                    user_workspace_path=require_authenticated_user_workspace_path(
                        current_user.get("workspace_path"),
                    ),
                )
            except ValidationError as error:
                raise_invalid_request(request, str(error), error_type="invalid_workspace_path")
        disallowed_unqualified_tools = load_automation_disallowed_unqualified_tools(
            api_context.dependencies.config,
        )
        try:
            next_mode = extract_agent_mode(merged_settings, strict=True)
        except ValidationError as error:
            raise_invalid_request(request, str(error), error_type="invalid_agent_mode")
        normalized_merged_settings = normalize_model_settings_mcp_for_owner(
            request,
            normalize_chat_execution_settings(merged_settings),
            is_automation=settings_authority.is_automation,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        )
        await require_agent_settings_update_allowed(
            request=request,
            api_context=api_context,
            conv_id=resolved_conv_id,
            user_id=current_user["id"],
            existing_settings=existing_settings,
            next_settings=normalized_merged_settings,
        )
        if _has_mcp_update(payload):
            normalized_merged_settings["mcp"] = await _merge_mcp_update_from_settings_patch(
                request=request,
                api_context=api_context,
                current_user=current_user,
                conv_id=resolved_conv_id,
                payload=payload,
                settings=normalized_merged_settings,
                disallowed_unqualified_tools=disallowed_unqualified_tools,
            )
        mcp_config = _require_mcp_config(request, normalized_merged_settings)
        validate_enabled_tools_for_agent_mode(
            request=request,
            settings=normalized_merged_settings,
            merged_config=mcp_config,
        )
        conversation_record = await update_conversation_model_settings(
            request,
            api_context=api_context,
            conv_id=resolved_conv_id,
            user_id=current_user["id"],
            model_settings=normalized_merged_settings,
        )
        if previous_mode != next_mode:
            await publish_agent_mode_changed_event(
                api_context,
                user_id=current_user["id"],
                conv_id=resolved_conv_id,
                mode=next_mode,
                logger=get_logger(LOGGER_NAME),
            )
    return conversation_record, previous_mode, next_mode


def _has_mcp_update(payload: ConversationSettingsUpdate) -> bool:
    model_settings = payload.model_settings
    if not isinstance(model_settings, dict):
        return False
    return isinstance(model_settings.get("mcp"), dict)


def _require_mcp_config(request: Request, model_settings: JSONDict) -> JSONDict:
    mcp_config = coerce_json_dict(model_settings.get("mcp"))
    if mcp_config is None:
        raise_server_error(
            request,
            "Conversation model_settings.mcp payload is invalid.",
            error_type="invalid_model_settings",
        )
    return mcp_config


async def _merge_mcp_update_from_settings_patch(
    *,
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    conv_id: str,
    payload: ConversationSettingsUpdate,
    settings: JSONDict,
    disallowed_unqualified_tools: tuple[str, ...],
) -> JSONDict:
    local_tool_catalog_scope = (
        INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE
        if current_user["is_admin"]
        else PUBLIC_MCP_TOOL_CATALOG_SCOPE
    )
    model_settings = payload.model_settings
    if not isinstance(model_settings, dict):
        return _require_mcp_config(request, settings)
    raw_updates = coerce_json_dict(model_settings.get("mcp"))
    if raw_updates is None:
        return _require_mcp_config(request, settings)
    tool_updates = {
        field_name: value
        for field_name, value in raw_updates.items()
        if field_name not in CONVERSATION_MCP_EXTENSION_FIELDS
    }
    if not tool_updates:
        return _require_mcp_config(request, settings)
    server_ids = (
        await load_mcp_server_ids(api_context.dependencies.database_mcp)
        if "server_configs" in tool_updates
        else set[str]()
    )
    model_id_override = coerce_optional_trimmed_str(model_settings.get("model"))
    state, tool_map = await load_conversation_mcp_catalog_state(
        request=request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
        local_tool_catalog_scope=local_tool_catalog_scope,
        model_id_override=model_id_override,
    )
    try:
        mcp_update = ConversationMCPConfigUpdate.model_validate(tool_updates)
    except pydantic.ValidationError as error:
        raise_invalid_request(request, str(error), error_type="invalid_request_error")
    return merge_conversation_mcp_config_update(
        request=request,
        state=state,
        payload=mcp_update,
        tool_map=tool_map,
        server_ids=server_ids,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
        extension_source=_require_mcp_config(request, settings),
    )
