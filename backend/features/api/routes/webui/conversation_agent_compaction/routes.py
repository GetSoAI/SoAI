"""SoAI - Manual compaction WebUI route registration [backend/features/api/routes/webui/conversation_agent_compaction/routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import ConflictError, ValidationError
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.logging.trace import get_logger
from features.api.routes.webui.conversation_agent_compaction.background import (
    start_manual_compaction_background_task,
)
from features.api.routes.webui.conversation_agent_compaction.regenerate_start_state import (
    resolve_manual_compaction_regenerate_start_state,
)
from features.api.routes.webui.conversation_agent_compaction.running_turns import (
    require_no_running_agent_turns,
)
from features.api.routes.webui.conversation_agent_compaction.start_state import (
    resolve_manual_compaction_start_state,
)
from features.api.routes.webui.conversation_message_write_outputs import (
    serialize_message_write_result,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_invalid_request
from features.api.schemas.agent_state import AgentCheckpointResponse
from features.api.schemas.conversations import (
    AgentCompactionBoundaryRemoveRequest,
    AgentCompactionRegenerateRequest,
    AgentCompactionStartRequest,
)

__all__ = ("register_compaction_route",)

LOGGER_NAME = "SoAI.features.api.routes"


def register_compaction_route(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/agent/compact/start",
        response_model=AgentCheckpointResponse,
    )
    async def start_agent_compaction(
        request: Request,
        conv_id: str,
        payload: AgentCompactionStartRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        start_state = await resolve_manual_compaction_start_state(
            request=request,
            api_context=api_context,
            current_user=current_user,
            conv_id=conv_id,
            payload=payload,
        )

        logger = get_logger(LOGGER_NAME)
        start_checkpoint_payload = await start_manual_compaction_background_task(
            request=request,
            api_context=api_context,
            current_user=current_user,
            start_state=start_state,
            logger=logger,
        )
        return JSONResponse(content=start_checkpoint_payload)

    @routers.webui.post(
        "/conversations/{conv_id}/agent/compact/remove-boundary",
    )
    async def remove_agent_compaction_boundary(
        request: Request,
        conv_id: str,
        payload: AgentCompactionBoundaryRemoveRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            await require_no_running_agent_turns(
                request,
                api_context=api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            write_result = (
                await api_context.dependencies.database_messages.remove_context_compaction_boundary(
                    conv_id,
                    current_user["id"],
                    assistant_turn_at_ms=payload.assistant_turn_at_ms,
                    model_variant_index=payload.model_variant_index,
                    tool_call_id=payload.tool_call_id,
                    expected_last_modified_at_ms=payload.expected_last_modified_at_ms,
                )
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        await publish_conversation_updated_and_message_saved(
            api_context.dependencies.event_bus,
            user_id=current_user["id"],
            conv_id=conv_id,
            message_count=write_result.message_count,
            last_modified_at_ms=write_result.last_modified_at_ms,
        )
        return JSONResponse(content=serialize_message_write_result(write_result))

    @routers.webui.post(
        "/conversations/{conv_id}/agent/compact/regenerate",
        response_model=AgentCheckpointResponse,
    )
    async def regenerate_agent_compaction(
        request: Request,
        conv_id: str,
        payload: AgentCompactionRegenerateRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        start_state = await resolve_manual_compaction_regenerate_start_state(
            request=request,
            api_context=api_context,
            current_user=current_user,
            conv_id=conv_id,
            payload=payload,
        )

        logger = get_logger(LOGGER_NAME)
        start_checkpoint_payload = await start_manual_compaction_background_task(
            request=request,
            api_context=api_context,
            current_user=current_user,
            start_state=start_state,
            logger=logger,
        )
        return JSONResponse(content=start_checkpoint_payload)
