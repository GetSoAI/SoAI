"""SoAI - Manual compaction WebUI route registration [backend/features/api/routes/webui/conversation_agent_compaction/routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.agent.turn_snapshot import require_agent_turn_snapshot
from core.errors.exceptions import ConflictError, ValidationError
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.api.routes.webui.conversation_agent_compaction.background import (
    start_manual_compaction_background_task,
)
from features.api.routes.webui.conversation_agent_compaction.regenerate_command import (
    build_manual_compaction_regeneration_command,
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
from features.api.routes.webui.conversation_agent_compaction.start_state_claims import (
    ManualCompactionStartState,
)
from features.api.routes.webui.conversation_lifecycle_admission import (
    require_idle_conversation_stream_lifecycle,
    run_idle_conversation_lifecycle_operation,
    run_tracked_conversation_admission,
)
from features.api.routes.webui.conversation_message_write_outputs import (
    serialize_message_write_result,
)
from features.api.runtime.agent_state_payloads import build_agent_checkpoint_payload
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
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


async def _read_manual_regeneration_replay(
    api_context: ApiContext,
    *,
    conv_id: str,
    user_id: int,
    payload: AgentCompactionRegenerateRequest,
) -> JSONDict | None:
    command = build_manual_compaction_regeneration_command(payload)
    if command is None or payload.client_id is None or payload.client_request_id is None:
        return None
    existing = await api_context.dependencies.database_agent_turns.get_manual_regeneration_attempt(
        conv_id=conv_id,
        user_id=user_id,
        client_id=payload.client_id,
        client_request_id=payload.client_request_id,
    )
    if existing is None:
        return None
    if existing.get("manual_regeneration_request") != command:
        raise ConflictError("Manual compaction regeneration identity command conflict.")
    return build_agent_checkpoint_payload(
        snapshot=require_agent_turn_snapshot(existing),
        subagent_snapshots=[],
    )


async def _commit_manual_compaction_start(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
    start_state: ManualCompactionStartState,
) -> JSONDict:
    async with api_context.dependencies.chat_stream_registry.lifecycle_lock(
        user_id=current_user["id"],
        conv_id=start_state.conv_id,
    ):
        await require_idle_conversation_stream_lifecycle(
            api_context,
            user_id=current_user["id"],
            conv_id=start_state.conv_id,
        )
        return await start_manual_compaction_background_task(
            request=request,
            api_context=api_context,
            current_user=current_user,
            start_state=start_state,
            logger=get_logger(LOGGER_NAME),
        )


async def _commit_manual_compaction_regeneration(
    request: Request,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
    payload: AgentCompactionRegenerateRequest,
    conv_id: str,
) -> JSONDict:
    async with api_context.dependencies.chat_stream_registry.lifecycle_lock(
        user_id=current_user["id"],
        conv_id=conv_id,
    ):
        replay = await _read_manual_regeneration_replay(
            api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
            payload=payload,
        )
        if replay is not None:
            return replay
        await require_idle_conversation_stream_lifecycle(
            api_context,
            user_id=current_user["id"],
            conv_id=conv_id,
        )
        start_state = await resolve_manual_compaction_regenerate_start_state(
            request=request,
            api_context=api_context,
            current_user=current_user,
            conv_id=conv_id,
            payload=payload,
        )
        return await start_manual_compaction_background_task(
            request=request,
            api_context=api_context,
            current_user=current_user,
            start_state=start_state,
            logger=get_logger(LOGGER_NAME),
        )


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
        conversation_context = await require_conversation_access_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        try:
            start_state = await resolve_manual_compaction_start_state(
                request=request,
                api_context=api_context,
                current_user=current_user,
                conv_id=conversation_context.resolved_conv_id,
                payload=payload,
            )
            start_checkpoint_payload = await run_tracked_conversation_admission(
                api_context,
                admission=_commit_manual_compaction_start(
                    request=request,
                    api_context=api_context,
                    current_user=current_user,
                    start_state=start_state,
                ),
                task_name=f"manual-compaction-start-admission-{conversation_context.resolved_conv_id}",
                cancellation_note="Manual compaction admission resolution failed",
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
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
        user_id = current_user["id"]
        try:
            await require_no_running_agent_turns(
                request,
                api_context=api_context,
                conv_id=conv_id,
                user_id=user_id,
            )
            write_result = await run_idle_conversation_lifecycle_operation(
                api_context,
                user_id=user_id,
                conv_id=conv_id,
                operation=lambda: api_context.dependencies.database_messages.remove_context_compaction_boundary(
                    conv_id,
                    user_id,
                    assistant_turn_at_ms=payload.assistant_turn_at_ms,
                    model_variant_index=payload.model_variant_index,
                    tool_call_id=payload.tool_call_id,
                    expected_last_modified_at_ms=payload.expected_last_modified_at_ms,
                ),
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        await publish_conversation_updated_and_message_saved(
            api_context.dependencies.event_bus,
            user_id=user_id,
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
        conversation_context = await require_conversation_access_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        try:
            replay = await _read_manual_regeneration_replay(
                api_context,
                conv_id=conversation_context.resolved_conv_id,
                user_id=current_user["id"],
                payload=payload,
            )
            if replay is not None:
                return JSONResponse(content=replay)
            start_checkpoint_payload = await run_tracked_conversation_admission(
                api_context,
                admission=_commit_manual_compaction_regeneration(
                    request=request,
                    api_context=api_context,
                    current_user=current_user,
                    payload=payload,
                    conv_id=conversation_context.resolved_conv_id,
                ),
                task_name=(
                    "manual-compaction-regeneration-admission-"
                    f"{payload.client_request_id or conversation_context.resolved_conv_id}"
                ),
                cancellation_note="Manual compaction admission resolution failed",
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        return JSONResponse(content=start_checkpoint_payload)
