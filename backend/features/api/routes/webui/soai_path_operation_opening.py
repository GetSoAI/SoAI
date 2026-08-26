"""SoAI - Conversation SoAI path open and token responses [backend/features/api/routes/webui/soai_path_operation_opening.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from starlette.responses import JSONResponse

from core.errors.exceptions import SecurityError, ValidationError
from core.workspaces.soai_path_link_codec import build_soai_path_token
from features.api.routes.webui.soai_path_operation_resolution import (
    ResolvedSoaiPath,
    SoaiPathRouteTarget,
    resolve_soai_path_route_target,
    unavailable_soai_path_response,
    user_virtual_path_for_soai_path,
)
from features.api.routes.webui.soai_path_operation_validation import (
    SoaiPathOperationRequest,
    no_store_headers,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser

__all__ = ("open_soai_path_response", "token_soai_path_response")


async def open_soai_path_response(
    *,
    request: Request,
    conv_id: str,
    body: SoaiPathOperationRequest,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> JSONResponse:
    target = SoaiPathRouteTarget(request, conv_id, body, current_user, api_context)
    resolved = await _resolve_virtual_soai_path_for_opening(
        target,
    )
    if isinstance(resolved, JSONResponse):
        return resolved
    _, user_virtual_path = resolved
    return JSONResponse(
        content={
            "state": "available",
            "virtual_path": user_virtual_path,
        },
        headers=no_store_headers(),
    )


async def token_soai_path_response(
    *,
    request: Request,
    conv_id: str,
    body: SoaiPathOperationRequest,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> JSONResponse:
    target = SoaiPathRouteTarget(request, conv_id, body, current_user, api_context)
    resolved = await _resolve_virtual_soai_path_for_opening(
        target,
    )
    if isinstance(resolved, JSONResponse):
        return resolved
    soai_path, user_virtual_path = resolved
    token = build_soai_path_token(
        virtual_path=user_virtual_path,
        label=str(soai_path.canonical.get("title") or "").strip() or None,
    )
    return JSONResponse(
        content={"state": "available", "token": token},
        headers=no_store_headers(),
    )


async def _resolve_virtual_soai_path_for_opening(
    target: SoaiPathRouteTarget,
) -> tuple[ResolvedSoaiPath, str] | JSONResponse:
    resolved = await resolve_soai_path_route_target(target)
    if isinstance(resolved, JSONResponse):
        return resolved
    try:
        user_virtual_path = user_virtual_path_for_soai_path(resolved.scope, resolved.canonical)
    except (OSError, SecurityError, ValidationError):
        return unavailable_soai_path_response()
    return resolved, user_virtual_path
