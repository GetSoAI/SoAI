"""SoAI - MCP management OAuth callback endpoint [backend/features/api/routes/mcp/routes/management_oauth_callback_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from core.errors.exceptions import ValidationError
from core.oauth.popup_html import build_popup_html
from core.oauth.state_tokens import (
    OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT,
    OAUTH_STATE_TOKEN_TYPE_MCP_SERVER,
    unwrap_oauth_flow_state_token,
)
from core.oauth.types import OAuthError
from core.system_api.route_paths import MCP_OAUTH_CALLBACK_ROUTE_PATH
from features.api.runtime.context import (
    ApiContext,
    get_current_user_optional,
    resolve_api_context,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_endpoints",)


async def mcp_oauth_callback(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> HTMLResponse:
    current_user = await get_current_user_optional(request)
    if current_user is None:
        error_payload: JSONDict = {"ok": False, "oauth_status": "error"}
        return _build_popup_response(
            error_payload,
        )
    code = request.query_params.get("code")
    state_token = request.query_params.get("state")
    if not code or not state_token:
        error_payload = {"ok": False, "oauth_status": "error"}
        return _build_popup_response(
            error_payload,
        )
    try:
        payload: JSONDict = await _complete_oauth_callback(
            api_context=api_context,
            code=code,
            state_token=state_token,
            user_id=current_user["id"],
        )
    except (OAuthError, ValidationError):
        payload = {"ok": False, "oauth_status": "error"}
    return _build_popup_response(payload)


async def _complete_oauth_callback(
    *,
    api_context: ApiContext,
    code: str,
    state_token: str,
    user_id: int,
) -> JSONDict:
    token_type, _ = unwrap_oauth_flow_state_token(state_token)
    if token_type == OAUTH_STATE_TOKEN_TYPE_MCP_SERVER:
        return await api_context.dependencies.mcp_remote.complete_oauth_callback(
            code=code,
            state_token=state_token,
            user_id=user_id,
        )
    if token_type == OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT:
        return await api_context.dependencies.external_accounts.complete_oauth_callback(
            code=code,
            state_token=state_token,
            user_id=user_id,
        )
    raise ValidationError("OAuth state token type is invalid.")


def _build_popup_response(payload: JSONDict) -> HTMLResponse:
    return HTMLResponse(status_code=200, content=build_popup_html(payload))


def register_endpoints(router: APIRouter) -> None:
    router.get(MCP_OAUTH_CALLBACK_ROUTE_PATH)(mcp_oauth_callback)
