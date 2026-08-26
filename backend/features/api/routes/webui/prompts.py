"""SoAI - Prompt Templates API routes [backend/features/api/routes/webui/prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from core.errors.exceptions import ValidationError
from core.events.types_webui import PromptListUpdatedEvent
from core.prompts.colors import validate_prompt_color
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request
from features.api.runtime.prompt_templates import (
    create_prompt,
    list_prompts,
    update_prompt,
)
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.webui_records import (
    webui_fetch_or_404,
    webui_require_true_or_404,
)
from features.api.schemas.prompts import (
    PromptBatchDeleteRequest,
    PromptCreate,
    PromptUpdate,
)

__all__ = (
    "PromptsRouteRegistrar",
    "register_routes",
)


async def _publish_prompts_updated(
    api_context: ApiContext,
    user_id: int,
) -> None:
    async with api_context.dependencies.prompts_update_locks[user_id]:
        prompts = await list_prompts(
            api_context.dependencies.webui_manager.database_prompts,
            user_id,
        )
        await api_context.dependencies.event_bus.publish(
            PromptListUpdatedEvent(user_id=user_id, color=None, prompts=prompts),
        )


class PromptsRouteRegistrar:

    def __init__(self, router: APIRouter) -> None:
        self.router = router

    def register(self) -> None:
        router = self.router

        @router.get("/prompts")
        async def handle_list_prompts(
            request: Request,
            color: str | None = Query(default=None),
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            try:
                normalized_color = validate_prompt_color(color)
            except (ValidationError, ValueError) as error:
                raise_invalid_request(request, str(error), error_type="invalid_color")

            prompts = await list_prompts(
                api_context.dependencies.webui_manager.database_prompts,
                current_user["id"],
                normalized_color,
            )
            return JSONResponse(content=prompts)

        @router.post("/prompts", status_code=201)
        async def handle_create_prompt(
            _request: Request,
            payload: PromptCreate,
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            created = await create_prompt(
                api_context.dependencies.webui_manager.database_prompts,
                current_user["id"],
                payload.name,
                payload.content,
                payload.color,
            )
            await _publish_prompts_updated(api_context, current_user["id"])
            return JSONResponse(content=created)

        @router.get("/prompts/{prompt_id}")
        async def handle_get_prompt(
            request: Request,
            prompt_id: str,
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            prompt = await webui_fetch_or_404(
                request,
                api_context.dependencies.webui_manager.database_prompts.get_prompt(
                    prompt_id,
                    current_user["id"],
                ),
                message="Prompt not found.",
            )
            return JSONResponse(content=prompt)

        @router.patch("/prompts/{prompt_id}")
        async def handle_update_prompt(
            request: Request,
            prompt_id: str,
            payload: PromptUpdate,
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            updated = await webui_fetch_or_404(
                request,
                update_prompt(
                    api_context.dependencies.webui_manager.database_prompts,
                    prompt_id,
                    current_user["id"],
                    payload.name,
                    payload.content,
                    payload.color,
                ),
                message="Prompt not found.",
            )
            await _publish_prompts_updated(api_context, current_user["id"])
            return JSONResponse(content=updated)

        @router.delete("/prompts/{prompt_id}", status_code=204)
        async def handle_delete_prompt(
            request: Request,
            prompt_id: str,
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            await webui_require_true_or_404(
                request,
                api_context.dependencies.webui_manager.database_prompts.delete_prompt(
                    prompt_id,
                    current_user["id"],
                ),
                message="Prompt not found.",
            )
            await _publish_prompts_updated(api_context, current_user["id"])
            return create_no_content_response()

        @router.post("/prompts/batch-delete")
        async def batch_delete_prompts(
            _: Request,
            payload: PromptBatchDeleteRequest,
            current_user: CurrentUser = Depends(get_current_user),
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> dict[str, int]:
            deleted = (
                await api_context.dependencies.webui_manager.database_prompts.delete_prompts_batch(
                    payload.ids,
                    current_user["id"],
                )
            )
            await _publish_prompts_updated(api_context, current_user["id"])
            return {"deleted": deleted}


def register_routes(routers: ApiRouters) -> None:
    _prompts_registrar = PromptsRouteRegistrar(routers.webui)
    _prompts_registrar.register()
