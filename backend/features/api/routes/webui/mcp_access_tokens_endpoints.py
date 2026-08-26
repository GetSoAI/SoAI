"""SoAI - MCP access token provisioning endpoints [backend/features/api/routes/webui/mcp_access_tokens_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, Response, status
from fastapi.responses import JSONResponse

from core.auth.mcp_access_tokens import (
    create_mcp_access_token,
    list_mcp_access_tokens,
    revoke_mcp_access_token,
)
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_not_found,
    raise_server_error,
    raise_service_unavailable,
)
from features.api.schemas.mcp_access_tokens import McpAccessTokenCreatePayload

__all__ = ("register_routes",)


async def handle_list_mcp_access_tokens(
    _request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    tokens = await list_mcp_access_tokens(
        api_context.dependencies.webui_manager.database_mcp_access_tokens,
        user_id=current_user["id"],
        include_revoked=True,
    )
    return JSONResponse(content={"tokens": tokens})


async def handle_create_mcp_access_token(
    request: Request,
    payload: McpAccessTokenCreatePayload,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    primary_signing_secret = api_context.dependencies.auth_config.primary_signing_secret
    if primary_signing_secret is None:
        raise_service_unavailable(request, "Authentication secret key is not configured.")
    created = await create_mcp_access_token(
        api_context.dependencies.webui_manager.database_mcp_access_tokens,
        user_id=current_user["id"],
        label=payload.label,
        expires_at_ms=payload.expires_at_ms,
        secret_key=primary_signing_secret,
    )
    token_value = created.get("token")
    metadata = created.get("metadata")
    if not isinstance(token_value, str) or not token_value:
        raise_server_error(request, "Created MCP token is missing its secret.")
    if not isinstance(metadata, dict):
        raise_server_error(request, "Created MCP token is missing metadata.")
    token_id_value = metadata.get("token_id")
    if not isinstance(token_id_value, str) or not token_id_value:
        raise_server_error(request, "Created MCP token is missing token_id.")
    log_audit_event(
        request,
        "CREATE_MCP_ACCESS_TOKEN",
        token_id_value,
        {"label": metadata.get("label"), "expires_at_ms": metadata.get("expires_at_ms")},
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"token": token_value, "metadata": metadata},
    )


async def handle_revoke_mcp_access_token(
    request: Request,
    token_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    token_store = api_context.dependencies.webui_manager.database_mcp_access_tokens
    existing = await token_store.get_token_by_id(token_id)
    owner_id = existing.get("user_id") if isinstance(existing, dict) else None
    if not isinstance(owner_id, int) or owner_id != current_user["id"]:
        raise_not_found(request, "Token not found.")
    revoked = await revoke_mcp_access_token(
        token_store,
        token_id,
        revoked_by=current_user["id"],
    )
    if not revoked:
        raise_not_found(request, "Token not found.")
    log_audit_event(
        request,
        "REVOKE_MCP_ACCESS_TOKEN",
        token_id,
        {"revoked_by": current_user.get("username")},
    )
    return JSONResponse(content={"token": revoked})


def register_routes(routers: ApiRouters) -> None:
    router = routers.webui
    router.get(
        "/mcp-access-tokens",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )(handle_list_mcp_access_tokens)
    router.post(
        "/mcp-access-tokens",
        status_code=201,
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )(handle_create_mcp_access_token)
    router.post(
        "/mcp-access-tokens/{token_id}/revoke",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )(handle_revoke_mcp_access_token)
