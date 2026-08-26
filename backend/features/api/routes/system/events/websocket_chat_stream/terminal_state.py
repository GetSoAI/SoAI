"""SoAI - WebSocket chat stream terminal turn-state resolution [backend/features/api/routes/system/events/websocket_chat_stream/terminal_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import JSONDict
from features.agent.runtime.turn_lifecycle.finalize import (
    resolve_exact_turn_noncritical,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.context import ApiContext
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("resolve_ws_chat_stream_terminal_turn_state",)


async def resolve_ws_chat_stream_terminal_turn_state(
    *,
    api_context: ApiContext,
    runtime: AssistantTimelineRuntime,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> JSONDict | None:
    resolved_trace_id = trace_id if trace_id is not None else runtime.request_id
    turn_state = await resolve_exact_turn_noncritical(
        database_agent_turns=api_context.dependencies.database_agent_turns,
        logger=logger,
        trace_id=resolved_trace_id,
        conv_id=runtime.conv_id,
        user_id=runtime.user_id,
        turn_id=runtime.agent_turn_id,
        request_id=runtime.request_id,
        operation="webui_ws_chat_stream.resolve_agent_turn_state",
        log_message="Failed to resolve agent turn state during chat stream finalization (non-critical).",
    )
    return turn_state
