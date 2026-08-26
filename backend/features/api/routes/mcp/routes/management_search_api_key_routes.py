"""SoAI - MCP management search API key routes [backend/features/api/routes/mcp/routes/management_search_api_key_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.state.access import AccessAction
from core.types.json_value import require_json_dict, require_json_dict_list
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_invalid_request, raise_not_found
from features.api.runtime.responses import create_no_content_response
from features.api.schemas.api_keys import SearchProviderApiKeyUpdate

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.mcp.get(
        "/search-api-keys",
        dependencies=require_action_dependencies(AccessAction.MCP_ADMIN),
    )
    async def list_mcp_search_api_keys(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        keys = (
            await api_context.dependencies.mcp_server.search_api_keys.list_search_provider_api_keys()
        )
        providers = api_context.dependencies.mcp_server.search.list_supported_providers()
        payload: JSONDict = {
            "keys": require_json_dict_list(keys, label="MCP search api keys"),
            "providers": list(providers),
        }
        return JSONResponse(content=payload)

    @routers.mcp.put(
        "/search-api-keys/{provider}",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.MCP_ADMIN),
    )
    async def set_mcp_search_api_key(
        request: Request,
        provider: str,
        payload: SearchProviderApiKeyUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            entry = await api_context.dependencies.mcp_server.search_api_keys.set_search_provider_api_key(
                provider,
                payload.api_key,
            )
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        log_audit_event(
            request,
            "MCP_SEARCH_API_KEY_SET",
            str(entry.get("provider") or provider),
            {"source": entry.get("source")},
        )
        return JSONResponse(content=require_json_dict(entry, label="MCP api key entry"))

    @routers.mcp.delete(
        "/search-api-keys/{provider}",
        status_code=204,
        dependencies=restart_protected_dependencies(AccessAction.MCP_ADMIN),
    )
    async def delete_mcp_search_api_key(
        request: Request,
        provider: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            deleted = await api_context.dependencies.mcp_server.search_api_keys.delete_search_provider_api_key(
                provider,
            )
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        if not deleted:
            raise_not_found(request, "Search provider API key not found.")
        log_audit_event(request, "MCP_SEARCH_API_KEY_DELETED", provider)
        return create_no_content_response()
