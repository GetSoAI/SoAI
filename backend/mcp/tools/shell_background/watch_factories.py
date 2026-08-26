"""SoAI - Shell background watch payload factories [backend/mcp/tools/shell_background/watch_factories.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallDependencies

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_shell_background_owned_task_metadata",
    "build_shell_background_streamer_dependencies",
)


def build_shell_background_streamer_dependencies(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    event_bus: EventBusProtocol,
    identity: CurrentToolCallIdentity,
    logger: LoggerProtocol,
    trace_id: str,
) -> DeferredToolCallDependencies:
    return DeferredToolCallDependencies(
        database_tool_calls=database_tool_calls,
        event_bus=event_bus,
        logger=logger,
        trace_id=trace_id,
        user_id=identity.user_id,
        conv_id=identity.conv_id,
        assistant_turn_at_ms=identity.assistant_turn_at_ms,
        model_variant_index=identity.model_variant_index,
        turn_id=str(identity.turn_id),
        iteration_index=int(identity.iteration_index) if identity.iteration_index else 0,
        call_id=identity.call_id,
        tool_name=identity.tool_name,
    )


def build_shell_background_owned_task_metadata(
    *,
    identity: CurrentToolCallIdentity,
    shell_session_id: int,
) -> JSONDict:
    return {
        "tool_name": identity.tool_name,
        "call_id": identity.call_id,
        "conv_id": identity.conv_id,
        "shell_session_id": int(shell_session_id),
    }
