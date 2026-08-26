"""SoAI - Canonical Chat settings admission for Messaging accounts [backend/features/api/runtime/messaging_account_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_model_settings_resolution import (
    resolve_conversation_model_settings,
)
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import AGENT_MCP_TOOL_SELECTION_FIELDS
from core.mcp.tool_catalog import collect_mcp_tool_map
from core.mcp.tool_catalog_scope import (
    INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE,
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
)
from core.model_settings.normalization import normalize_chat_execution_settings
from core.model_settings.request_projection import build_chat_execution_openai_request
from core.openai.model_settings_validation import validate_model_settings
from core.types.json_value import coerce_json_dict
from core.workspaces.model_settings_workspace_path import (
    apply_model_settings_workspace_path_update,
)
from core.workspaces.user_workspace_path import (
    require_authenticated_user_workspace_path,
    resolve_user_record_workspace_access,
)
from features.api.runtime.errors import raise_invalid_request, raise_server_error
from features.api.runtime.mcp_enabled_mode_validation import (
    validate_enabled_tools_for_agent_mode,
)
from features.api.runtime.mcp_server_configs_validation import normalize_server_configs
from features.api.runtime.mcp_tool_selection_validation import (
    normalize_selected_mcp_tools,
)
from features.api.runtime.model_settings_mcp import normalize_model_settings_mcp
from features.api.runtime.user_coercion import current_user_to_json_dict

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser

__all__ = ("normalize_messaging_account_model_settings",)


async def normalize_messaging_account_model_settings(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    current_user: CurrentUser,
    model_settings: JSONDict,
) -> JSONDict:
    try:
        validated = validate_model_settings(model_settings)
        _reject_multi_variant_settings(request, validated)
        validated = _normalize_workspace_path(
            api_context=api_context,
            current_user=current_user,
            model_settings=validated,
        )
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)
    normalized = normalize_model_settings_mcp(request, validated)
    normalized = await resolve_conversation_model_settings(
        user_id=current_user["id"],
        model_settings_snapshot=normalized,
        database_chat_identity_defaults=(api_context.dependencies.database_chat_identity_defaults),
        database_chat_model_defaults=api_context.dependencies.database_chat_model_defaults,
    )
    normalized = normalize_chat_execution_settings(normalized)
    mcp_config = coerce_json_dict(normalized.get("mcp"))
    if mcp_config is None:
        raise_server_error(request, "Normalized Chat MCP settings are invalid.")
    normalized_mcp = await _validate_mcp_catalog_selection(
        request=request,
        api_context=api_context,
        current_user=current_user,
        mcp_config=mcp_config,
    )
    normalized["mcp"] = normalized_mcp
    validate_enabled_tools_for_agent_mode(
        request=request,
        settings=normalized,
        merged_config=normalized_mcp,
    )
    return normalized


def _reject_multi_variant_settings(
    request: RequestProtocol,
    model_settings: JSONDict,
) -> None:
    comparison_models = model_settings.get("comparison_models")
    if isinstance(comparison_models, list) and comparison_models:
        raise_invalid_request(
            request,
            "Messaging account settings cannot contain comparison models.",
        )
    completion_count = build_chat_execution_openai_request(model_settings).get("n")
    if (
        not isinstance(completion_count, bool)
        and isinstance(completion_count, int | float)
        and completion_count > 1
    ):
        raise_invalid_request(
            request,
            "Messaging account settings cannot request more than one completion.",
        )


def _normalize_workspace_path(
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
    model_settings: JSONDict,
) -> JSONDict:
    if "workspace_path" not in model_settings:
        return model_settings
    resolve_user_record_workspace_access(
        api_context.dependencies.files,
        current_user_to_json_dict(current_user),
    )
    return apply_model_settings_workspace_path_update(
        files=api_context.dependencies.files,
        model_settings=model_settings,
        raw_workspace_path=model_settings.get("workspace_path"),
        user_workspace_path=require_authenticated_user_workspace_path(
            current_user.get("workspace_path"),
        ),
    )


async def _validate_mcp_catalog_selection(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    current_user: CurrentUser,
    mcp_config: JSONDict,
) -> JSONDict:
    local_scope = (
        INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE
        if current_user["is_admin"]
        else PUBLIC_MCP_TOOL_CATALOG_SCOPE
    )
    tool_map = await collect_mcp_tool_map(
        api_context.dependencies.mcp_server,
        api_context.dependencies.mcp_remote,
        api_context.dependencies.mcp_tool_catalog_cache,
        local_scope=local_scope,
    )
    all_servers = await api_context.dependencies.database_mcp.get_all_mcp_servers()
    server_ids = {
        server_id.strip()
        for server in all_servers
        if isinstance((server_id := server.get("id")), str) and server_id.strip()
    }
    normalized: JSONDict = dict(mcp_config)
    normalized["server_configs"] = normalize_server_configs(
        request=request,
        server_configs=mcp_config.get("server_configs"),
        server_ids=server_ids,
    )
    for field_name in AGENT_MCP_TOOL_SELECTION_FIELDS:
        normalized[field_name] = normalize_selected_mcp_tools(
            request=request,
            raw_tools=mcp_config.get(field_name),
            field_name=field_name,
            tool_map=tool_map,
            server_configs=normalized["server_configs"],
            reject_empty=mcp_config.get("tools_enabled") is True,
        )
    return normalized
