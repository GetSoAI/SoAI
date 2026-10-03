"""SoAI - Conversation regeneration status routes [backend/features/api/routes/webui/conversation_message_regeneration_status_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import JSONResponse, Response

from core.types.json import JSONDict
from features.api.routes.webui.conversation_message_regeneration_receipts import (
    serialize_conversation_regeneration_attempt,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request, raise_not_found

__all__ = ("register_routes",)


async def _read_conversation_regeneration_attempt(
    request: Request,
    *,
    conv_id: str,
    user_id: int,
    api_context: ApiContext,
    client_id: str | None = None,
    client_request_id: str | None = None,
) -> JSONDict | None:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    return await api_context.dependencies.database_regenerations.get_attempt(
        conv_id=conversation_context.resolved_conv_id,
        user_id=user_id,
        client_id=client_id,
        client_request_id=client_request_id,
    )


async def get_conversation_regeneration_status(
    request: Request,
    conv_id: str,
    client_id: str | None = Query(default=None, min_length=1, max_length=128),
    client_request_id: str | None = Query(default=None, min_length=1, max_length=128),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    if (client_id is None) != (client_request_id is None):
        raise_invalid_request(
            request,
            "Regeneration status requires both client_id and client_request_id.",
        )
    attempt = await _read_conversation_regeneration_attempt(
        request,
        conv_id=conv_id,
        user_id=current_user["id"],
        api_context=api_context,
        client_id=client_id,
        client_request_id=client_request_id,
    )
    if attempt is None:
        raise_not_found(request, "Conversation regeneration attempt was not found.")
    return JSONResponse(content=serialize_conversation_regeneration_attempt(attempt))


async def get_latest_conversation_regeneration_status(
    request: Request,
    conv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    attempt = await _read_conversation_regeneration_attempt(
        request,
        conv_id=conv_id,
        user_id=current_user["id"],
        api_context=api_context,
    )
    if attempt is None:
        return JSONResponse(content={"status": "no_attempt"})
    return JSONResponse(
        content={
            "status": "attempt",
            "attempt": serialize_conversation_regeneration_attempt(attempt),
        },
    )


def register_routes(routers: ApiRouters) -> None:
    router: APIRouter = routers.webui
    router.get("/conversations/{conv_id}/messages/regenerate/status")(
        get_conversation_regeneration_status,
    )
    router.get("/conversations/{conv_id}/messages/regenerate/latest-status")(
        get_latest_conversation_regeneration_status,
    )
