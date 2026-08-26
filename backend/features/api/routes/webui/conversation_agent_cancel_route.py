"""SoAI - Agent turn cancellation WebUI route registration [backend/features/api/routes/webui/conversation_agent_cancel_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request

from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.agent.turn_snapshot import require_agent_turn_snapshot
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.cancellation import publish_cancel
from features.api.runtime.automation_run_cancellation import (
    publish_automation_run_cancellation_for_conversation,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_not_found
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.agent_state import AgentTurnCancelRequest, AgentTurnCancelResponse
from features.chat.conversation_input_cancellation import (
    prepare_forced_steers_before_cancellation,
)

__all__ = ("register_cancel_route",)

LOGGER_NAME = "SoAI.features.api.conversation_agent_cancel_route"
OPERATION_CLEANUP_SHELL_SESSIONS = "webui.conversation_agent.cancel.cleanup_shell_sessions"


def register_cancel_route(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/agent/turns/{turn_id}/cancel",
        response_model=AgentTurnCancelResponse,
    )
    async def cancel_agent_turn(
        request: Request,
        conv_id: str,
        turn_id: str,
        payload: AgentTurnCancelRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AgentTurnCancelResponse:
        conversation_context = await require_conversation_access_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        turn_record = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_agent_turns.get_turn(
                conv_id=conversation_context.resolved_conv_id,
                user_id=current_user["id"],
                turn_id=turn_id,
            ),
            message="Agent turn not found.",
        )
        turn_snapshot = require_agent_turn_snapshot(turn_record)
        if turn_snapshot.turn_id != turn_id or turn_snapshot.turn_scope != TURN_SCOPE_ROOT:
            raise_not_found(request, "Agent turn not found.")
        status = turn_snapshot.status
        if status != "running":
            return AgentTurnCancelResponse(
                conv_id=conversation_context.resolved_conv_id,
                turn_id=turn_id,
                iteration_index=turn_snapshot.iteration_index,
                sequence=turn_snapshot.sequence,
                status="already_terminal",
                terminal_status=status,
            )
        cancellation_ids: list[str] = []
        for candidate in (
            turn_snapshot.turn_cancellation_id,
            turn_snapshot.active_inference_cancellation_id,
        ):
            if candidate is None:
                continue
            if candidate in cancellation_ids:
                continue
            cancellation_ids.append(candidate)
        if not cancellation_ids:
            raise_conflict(request, "No cancellable operation was found for this turn.")
        if payload.force_pending_steers:
            await prepare_forced_steers_before_cancellation(
                api_context.dependencies,
                user_id=current_user["id"],
                conv_id=conversation_context.resolved_conv_id,
                agent_turn_id=turn_id,
            )
        for cancellation_id in cancellation_ids:
            await publish_cancel(
                api_context.dependencies.event_bus,
                api_context.dependencies.cancellation_coordinator,
                api_context.dependencies.cancellation_history,
                request.state.context,
                "Agent turn cancellation requested.",
                cancellation_id=cancellation_id,
            )
        await publish_automation_run_cancellation_for_conversation(
            request,
            api_context,
            conversation_record=conversation_context.record,
            user_id=current_user["id"],
            conv_id=conversation_context.resolved_conv_id,
            reason="Automation run cancellation requested from chat stop.",
        )
        logger = get_logger(LOGGER_NAME)
        context = request.state.context

        async def cleanup_shell_sessions() -> None:
            try:
                await api_context.dependencies.mcp_server.cancel_openai_shell_sessions(
                    user_id=current_user["id"],
                    conv_id=conversation_context.resolved_conv_id,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to cancel OpenAI shell sessions after agent turn cancellation (non-critical).",
                    trace_id=context.trace_id,
                    operation=OPERATION_CLEANUP_SHELL_SESSIONS,
                    level="debug",
                    details={
                        "user_id": current_user["id"],
                        "conv_id": conversation_context.resolved_conv_id,
                        "turn_id": turn_id,
                    },
                )

        cleanup_task = create_ephemeral_task(
            cleanup_shell_sessions(),
            name=f"agent-turn-cancel-shell-cleanup-{conversation_context.resolved_conv_id}",
        )
        api_context.dependencies.application_control.track_background_task(cleanup_task)
        terminated_shell_sessions = 0
        return AgentTurnCancelResponse(
            conv_id=conversation_context.resolved_conv_id,
            turn_id=turn_id,
            iteration_index=turn_snapshot.iteration_index,
            sequence=turn_snapshot.sequence,
            status="cancellation_requested",
            cancellation_ids=cancellation_ids,
            terminated_shell_sessions=terminated_shell_sessions,
        )
