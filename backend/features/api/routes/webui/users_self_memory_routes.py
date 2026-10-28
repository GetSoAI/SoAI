"""SoAI - WebUI self-service memory routes [backend/features/api/routes/webui/users_self_memory_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.memory import (
    ChatMemoryProfileUpdate,
    MemoryEntryCreate,
    MemoryEntryUpdate,
    MemoryRelationUpdate,
)
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
            current_user["id"],
            payload.model_dump(
                exclude={"expected_revision"}, exclude_unset=payload.expected_revision is not None
            ),
            payload.expected_revision,
        )
        return JSONResponse(content=response_payload)

    @routers.webui.get("/users/me/memory/entries")
    async def get_my_memory_library(
        _request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            content=await api_context.dependencies.database_memory.read_library(current_user["id"])
        )

    @routers.webui.get("/users/me/memory/entries/{entry_id}")
    async def get_my_memory_entry(
        _request: Request,
        entry_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            content=await api_context.dependencies.database_memory.read_entry(
                current_user["id"], entry_id
            )
        )

    @routers.webui.post("/users/me/memory/entries", status_code=201)
    async def create_my_memory_entry(
        _request: Request,
        payload: MemoryEntryCreate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            status_code=201,
            content=await api_context.dependencies.database_memory.create_entry(
                current_user["id"], payload.id, payload.name, payload.content
            ),
        )

    @routers.webui.patch("/users/me/memory/entries/{entry_id}")
    async def update_my_memory_entry(
        _request: Request,
        entry_id: str,
        payload: MemoryEntryUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            content=await api_context.dependencies.database_memory.update_entry(
                current_user["id"],
                entry_id,
                payload.expected_revision,
                payload.name,
                payload.observation.model_dump() if payload.observation else None,
            )
        )

    @routers.webui.delete("/users/me/memory/entries/{entry_id}")
    async def delete_my_memory_entry(
        _request: Request,
        entry_id: str,
        expected_revision: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            content=await api_context.dependencies.database_memory.delete_entry(
                current_user["id"], entry_id, expected_revision
            )
        )

    @routers.webui.delete("/users/me/memory/entries/{entry_id}/observations/{observation_id}")
    async def delete_my_memory_observation(
        _request: Request,
        entry_id: str,
        observation_id: str,
        expected_revision: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            content=await api_context.dependencies.database_memory.delete_observation(
                current_user["id"], entry_id, observation_id, expected_revision
            )
        )

    @routers.webui.patch("/users/me/memory/entries/{entry_id}/relations/{relation_id}")
    async def update_my_memory_relation(
        _request: Request,
        entry_id: str,
        relation_id: str,
        payload: MemoryRelationUpdate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            content=await api_context.dependencies.database_memory.update_relation(
                current_user["id"],
                entry_id,
                relation_id,
                payload.expected_revision,
                payload.from_entity_id,
                payload.to_entity_id,
                payload.relation_type,
            )
        )

    @routers.webui.delete("/users/me/memory/entries/{entry_id}/relations/{relation_id}")
    async def delete_my_memory_relation(
        _request: Request,
        entry_id: str,
        relation_id: str,
        expected_revision: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(
            content=await api_context.dependencies.database_memory.delete_relation(
                current_user["id"], entry_id, relation_id, expected_revision
            )
        )
