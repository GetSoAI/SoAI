"""SoAI - Conversation web search state loading and validation [backend/features/api/routes/webui/conversation_web_search_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.mcp.protocols_main import MCPSearchProtocol
from core.types.json_value import coerce_json_dict
from features.api.routes.webui.conversation_web_search_payloads import (
    build_web_search_config_payload,
    normalize_search_results,
    read_available_providers,
    read_default_provider,
    read_max_results,
    require_supported_provider_input,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.conversation_access import resolve_conversation_access_id
from features.api.runtime.errors import (
    raise_server_error,
    raise_service_unavailable,
)
from features.api.runtime.validation import (
    require_conversation_model_settings_payload,
    require_optional_json_dict,
)
from features.api.runtime.webui_records import webui_fetch_or_404

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_web_search_config_payload",
    "load_web_search_context",
    "normalize_search_results",
    "read_available_providers",
    "read_default_provider",
    "read_max_results",
    "require_supported_provider_input",
)


async def load_web_search_context(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
) -> tuple[str, JSONDict, MCPSearchProtocol, JSONDict, JSONDict, JSONDict]:
    conversation_record = await webui_fetch_or_404(
        request,
        api_context.dependencies.database_conversations.get_conversation(conv_id, user_id),
        message="Conversation not found.",
    )
    conversation_record_json = coerce_json_dict(conversation_record)
    if conversation_record_json is None:
        raise_server_error(request, "Conversation payload is invalid.")
    resolved_conv_id = resolve_conversation_access_id(conversation_record_json, conv_id)
    search_engine = require_search_engine(request, api_context)
    settings = require_conversation_model_settings_payload(
        request,
        conversation_record_json.get("model_settings"),
    )
    mcp_config = require_optional_json_dict(
        request,
        settings.get("mcp"),
        field="model_settings.mcp",
    )
    search_config = require_optional_json_dict(
        request,
        mcp_config.get("web_search"),
        field="model_settings.mcp.web_search",
    )
    return (
        resolved_conv_id,
        conversation_record_json,
        search_engine,
        settings,
        mcp_config,
        search_config,
    )


def require_search_engine(request: Request, api_context: ApiContext) -> MCPSearchProtocol:
    search_engine = api_context.dependencies.mcp_server.search
    if search_engine is None:
        raise_service_unavailable(
            request,
            "Search engine is not available.",
        )
    return search_engine
