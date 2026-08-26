"""SoAI - Conversation web search endpoint handlers [backend/features/api/routes/webui/conversation_web_search_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.runtime.network_policy import OfflineModeError, require_online_mode
from features.api.routes.webui.conversation_web_search_state import (
    build_web_search_config_payload,
    load_web_search_context,
    normalize_search_results,
    read_available_providers,
    read_default_provider,
    read_max_results,
    require_supported_provider_input,
)
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_model_settings import (
    update_conversation_model_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_offline_mode
from features.api.schemas.web_search import WebSearchConfigUpdate, WebSearchRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "execute_web_search",
    "get_web_search_config",
    "update_web_search_config",
)


async def get_web_search_config(
    request: Request,
    conv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONDict:
    resolved_conv_id, _conversation_record, search_engine, _settings, _mcp_config, search_config = (
        await load_web_search_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
    )
    return build_web_search_config_payload(
        request,
        conv_id=resolved_conv_id,
        search_engine=search_engine,
        search_config=search_config,
    )


async def update_web_search_config(
    request: Request,
    conv_id: str,
    payload: WebSearchConfigUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONDict:
    resolved_conv_id, _record, _engine, _settings, _mcp, _search = await load_web_search_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    async with api_context.dependencies.conversation_agent_settings_locks.lock(
        (current_user["id"], resolved_conv_id),
    ):
        return await _update_web_search_config_locked(
            request=request,
            resolved_conv_id=resolved_conv_id,
            payload=payload,
            current_user=current_user,
            api_context=api_context,
        )


async def _update_web_search_config_locked(
    *,
    request: Request,
    resolved_conv_id: str,
    payload: WebSearchConfigUpdate,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> JSONDict:
    authoritative_conv_id, _record, search_engine, settings, mcp_config, search_config = (
        await load_web_search_context(
            request,
            api_context=api_context,
            conv_id=resolved_conv_id,
            user_id=current_user["id"],
        )
    )
    available_providers = read_available_providers(request, search_engine)
    updates = payload.model_dump(exclude_unset=True)
    if "enabled" in updates:
        enabled_value = updates.get("enabled")
        if enabled_value is None:
            search_config.pop("enabled", None)
        else:
            search_config["enabled"] = enabled_value
    if "default_provider" in updates:
        provider_value = updates.get("default_provider")
        if provider_value is None:
            search_config.pop("default_provider", None)
        else:
            search_config["default_provider"] = require_supported_provider_input(
                request,
                available_providers,
                provider=provider_value,
                field_name="default_provider",
            )
    if "max_results" in updates:
        max_results_value = updates.get("max_results")
        if max_results_value is None:
            search_config.pop("max_results", None)
        else:
            search_config["max_results"] = max_results_value
    response_payload = build_web_search_config_payload(
        request,
        conv_id=authoritative_conv_id,
        search_engine=search_engine,
        search_config=search_config,
    )
    mcp_config["web_search"] = search_config
    settings["mcp"] = mcp_config
    await update_conversation_model_settings(
        request,
        api_context=api_context,
        conv_id=authoritative_conv_id,
        user_id=current_user["id"],
        model_settings=settings,
    )
    return response_payload


async def execute_web_search(
    request: Request,
    conv_id: str,
    payload: WebSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    resolved_conv_id, _conversation_record, search_engine, _settings, _mcp_config, search_config = (
        await load_web_search_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
    )
    available_providers = read_available_providers(request, search_engine)
    provider = payload.provider
    if isinstance(provider, str):
        provider = require_supported_provider_input(
            request,
            available_providers,
            provider=provider,
            field_name="provider",
        )
    else:
        provider = read_default_provider(
            request,
            search_engine,
            search_config,
            available_providers,
        )
    max_results = (
        payload.max_results
        if payload.max_results is not None
        else read_max_results(request, search_config)
    )
    try:
        require_online_mode(api_context.dependencies.runtime_flags, source="web_search")
        results = await search_engine.search(
            query=payload.query,
            max_results=max_results,
            provider=provider,
            user_id=current_user["id"],
            owner_id=resolved_conv_id,
            owner_type="conversation",
        )
    except OfflineModeError as exception:
        raise_offline_mode(request, str(exception))
    normalized_results = normalize_search_results(request, results)
    return JSONResponse(
        content={
            "query": payload.query,
            "provider": provider,
            "results": normalized_results,
            "count": len(normalized_results),
        },
    )
