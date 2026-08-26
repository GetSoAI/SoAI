"""SoAI - Agent todo WebUI route registration [backend/features/api/routes/webui/conversation_agent_todo_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from features.api.routes.webui.conversation_agent_state_route_support import (
    AGENT_STATE_MANUAL_EDIT_EXCEPTIONS,
    raise_manual_edit_error,
    resolve_agent_todo_edit_context,
    respond_with_persisted_agent_state,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.schemas.agent_state import AgentTodoStateResponse

__all__ = ("register_todo_route",)

OPERATION = "webui.agent_todo.publish_todo_updated"


def register_todo_route(routers: ApiRouters) -> None:
    @routers.webui.patch(
        "/conversations/{conv_id}/agent/todo",
        response_model=AgentTodoStateResponse,
    )
    async def patch_agent_todo(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        resolved_conv_id, body, service = await resolve_agent_todo_edit_context(
            request,
            api_context,
            conv_id,
            current_user,
        )
        try:
            persisted = await service.persist_todo_state(
                conv_id=resolved_conv_id,
                user_id=current_user["id"],
                turn_id="",
                iteration_index=0,
                todo_value=body.get("todo"),
                explanation_value=body.get("explanation"),
                require_no_running_root_turn=True,
            )
        except AGENT_STATE_MANUAL_EDIT_EXCEPTIONS as exception:
            raise_manual_edit_error(request, exception, state_name="Todo")
        return await respond_with_persisted_agent_state(
            api_context,
            persisted,
            operation=OPERATION,
        )
