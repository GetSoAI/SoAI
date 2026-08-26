"""SoAI - MCP management OAuth status endpoints [backend/features/api/routes/mcp/routes/management_oauth_status_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from core.errors.exceptions import StateError, ValidationError
from core.external_accounts.oauth_updates import build_oauth_disconnect_updates
from core.external_accounts.state import resolve_effective_oauth_status
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.mcp.routes.management_server_rows import (
    load_mcp_server_row_or_raise,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_server_error,
)

__all__ = ("register_endpoints",)


async def clear_mcp_oauth(
    request: Request,
    server_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    normalized_server_id, _server_row = await load_mcp_server_row_or_raise(
        request,
        api_context,
        server_id=server_id,
        decrypt_key=True,
    )
    try:
        await api_context.dependencies.mcp_remote.disconnect_from_server(normalized_server_id)
        updated_row = await api_context.dependencies.database_mcp.update_mcp_server(
            normalized_server_id,
            {
                "auth_type": "oauth",
                **build_oauth_disconnect_updates(),
            },
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except StateError as exception:
        raise_server_error(request, str(exception), error_type="invalid_server_state")
    if updated_row is None:
        raise_server_error(
            request,
            f"MCP server '{normalized_server_id}' disappeared during OAuth clear.",
            error_type="invalid_server_state",
        )
    updated_status = await api_context.dependencies.database_mcp.update_mcp_server_status(
        normalized_server_id,
        "disconnected",
    )
    if not updated_status:
        raise_server_error(
            request,
            f"MCP server '{normalized_server_id}' disappeared during OAuth status update.",
            error_type="invalid_server_state",
        )
    return JSONResponse(content={"status": "cleared"})


async def get_mcp_oauth_status(
    request: Request,
    server_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    _normalized_server_id, server_row = await load_mcp_server_row_or_raise(
        request,
        api_context,
        server_id=server_id,
        decrypt_key=False,
    )
    oauth_status_value = server_row.get("oauth_status")
    expires_value = server_row.get("oauth_expires_at_ms")
    required_scopes_value = server_row.get("oauth_required_scopes")
    required_present = (
        bool(required_scopes_value) if isinstance(required_scopes_value, list) else False
    )
    last_error_value = server_row.get("last_error")
    try:
        oauth_status = resolve_effective_oauth_status(
            oauth_status=oauth_status_value,
            oauth_expires_at_ms=expires_value,
            has_refresh_token=server_row.get("oauth_has_refresh_token") is True,
            now_ms=epoch_ms(),
        )
    except StateError as exception:
        raise_server_error(request, str(exception), error_type="invalid_server_state")
    return JSONResponse(
        content={
            "oauth_status": oauth_status,
            "expires_at_ms": (
                int(expires_value)
                if isinstance(expires_value, int | float) and not isinstance(expires_value, bool)
                else None
            ),
            "required_scopes_present": required_present,
            "last_error": last_error_value if isinstance(last_error_value, str) else None,
        },
    )


def register_endpoints(router: APIRouter) -> None:
    router.post(
        "/servers/{server_id}/oauth/clear",
        dependencies=require_action_dependencies(AccessAction.MCP_ADMIN),
    )(clear_mcp_oauth)
    router.get(
        "/servers/{server_id}/oauth/status",
        dependencies=require_action_dependencies(AccessAction.MCP_ADMIN),
    )(get_mcp_oauth_status)
