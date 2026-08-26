"""SoAI - MCP management OAuth start endpoint [backend/features/api/routes/mcp/routes/management_oauth_start_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from core.errors.exceptions import StateError, ValidationError
from core.oauth.types import OAuthError
from core.state.access import AccessAction
from features.api.routes.mcp.route_errors import (
    build_mcp_management_error_response,
)
from features.api.routes.mcp.routes.management_server_rows import (
    load_mcp_server_row_or_raise,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.context import (
    ApiContext,
    get_current_user_optional,
    resolve_api_context,
)
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_server_error,
)

__all__ = ("register_endpoints",)


async def start_mcp_oauth(
    request: Request,
    server_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    current_user = await get_current_user_optional(request)
    if current_user is None:
        return build_mcp_management_error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Authentication required.",
        )
    normalized_server_id, server_row = await load_mcp_server_row_or_raise(
        request,
        api_context,
        server_id=server_id,
        decrypt_key=True,
    )
    if server_row.get("transport_type") != "streamable_http":
        raise_invalid_request(request, "OAuth is only supported for Streamable HTTP MCP servers.")
    try:
        result = await api_context.dependencies.mcp_remote.start_oauth_authorization(
            server_id=normalized_server_id,
            user_id=current_user["id"],
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except OAuthError as exception:
        raise_invalid_request(request, str(exception))
    except StateError as exception:
        raise_server_error(request, str(exception), error_type="invalid_server_state")
    return JSONResponse(content=result)


def register_endpoints(router: APIRouter) -> None:
    router.post(
        "/servers/{server_id}/oauth/start",
        dependencies=require_action_dependencies(AccessAction.MCP_ADMIN),
    )(start_mcp_oauth)
