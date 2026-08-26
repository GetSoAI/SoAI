"""SoAI - Current-user chat prompt history routes [backend/features/api/routes/webui/chat_prompt_history_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends
from starlette.responses import JSONResponse, Response

from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.responses import create_no_content_response
from features.api.schemas.chat_prompt_history import ChatPromptHistoryResponse

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/prompt-history",
        response_model=ChatPromptHistoryResponse,
    )
    async def list_prompt_history(
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        prompts = await api_context.dependencies.database_chat_prompt_history.list_prompts(
            user_id=current_user["id"],
        )
        return JSONResponse(content={"prompts": prompts})

    @routers.webui.delete("/prompt-history", status_code=204)
    async def clear_prompt_history(
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        await api_context.dependencies.database_chat_prompt_history.clear(
            user_id=current_user["id"],
        )
        return create_no_content_response()
