"""SoAI - WebUI self-service memory routes [backend/features/api/routes/webui/users_self_memory_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.memory import ChatMemoryProfileUpdate
from features.memory.user_profile_service import (
    read_user_memory_snapshot,
    save_user_profile_memory,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/users/me/memory")
    async def get_my_memory(
        _request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        payload = await read_user_memory_snapshot(
            api_context.dependencies.database_memory,
            api_context.dependencies.database_chat_identity_defaults,
            api_context.dependencies.database_users,
            current_user["id"],
        )
        return JSONResponse(content=payload)

    @routers.webui.put("/users/me/memory/chat-profile")
    async def update_my_chat_memory_profile(
        _request: Request,
        payload: ChatMemoryProfileUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        response_payload = await save_user_profile_memory(
            api_context.dependencies.database_memory,
            api_context.dependencies.database_chat_identity_defaults,
            api_context.dependencies.database_users,
            current_user["id"],
            payload.model_dump(),
        )
        return JSONResponse(content=response_payload)
