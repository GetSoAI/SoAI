"""SoAI - Shared assistant timeline terminal tool-call persistence resolution [backend/features/assistant_timeline/tool_call_terminal_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.assistant_timeline.tool_event_layout import resolve_tool_call_identity

if TYPE_CHECKING:
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "finalize_persisted_tool_call_if_unfinished",
    "resolve_persisted_tool_call",
)


async def resolve_persisted_tool_call(
    *,
    runtime: AssistantTimelineRuntime,
    database_tool_calls: DatabaseToolCallsProtocol,
    call_id: str,
) -> JSONDict | None:
    await runtime.require_mutation_allowed()
    identity = resolve_tool_call_identity(runtime, call_id)
    if identity is not None:
        return await database_tool_calls.get_tool_call_by_identity(
            conv_id=runtime.conv_id,
            call_id=call_id,
            turn_id=identity.turn_id,
            iteration_index=identity.iteration_index,
            message_index=identity.message_index,
            assistant_turn_at_ms=identity.assistant_identity.assistant_turn_at_ms,
            model_variant_index=identity.assistant_identity.model_variant_index,
        )
    return await database_tool_calls.get_tool_call_by_identity(
        conv_id=runtime.conv_id,
        call_id=call_id,
        turn_id=runtime.agent_turn_id,
        iteration_index=None,
        message_index=runtime.message_index,
        assistant_turn_at_ms=runtime.assistant_turn_at_ms,
        model_variant_index=runtime.model_variant_index,
    )


async def finalize_persisted_tool_call_if_unfinished(
    *,
    runtime: AssistantTimelineRuntime,
    database_tool_calls: DatabaseToolCallsProtocol,
    call_id: str,
    status: str,
    error_message: str | None,
    completed_at_ms: int,
) -> JSONDict | None:
    identity = resolve_tool_call_identity(runtime, call_id)
    if identity is not None:
        return await database_tool_calls.finalize_tool_call_if_unfinished_by_identity(
            conv_id=runtime.conv_id,
            call_id=call_id,
            turn_id=identity.turn_id,
            iteration_index=identity.iteration_index,
            message_index=identity.message_index,
            assistant_turn_at_ms=identity.assistant_identity.assistant_turn_at_ms,
            model_variant_index=identity.assistant_identity.model_variant_index,
            status=status,
            error_message=error_message,
            completed_at_ms=completed_at_ms,
        )
    return await database_tool_calls.finalize_tool_call_if_unfinished_by_identity(
        conv_id=runtime.conv_id,
        call_id=call_id,
        turn_id=runtime.agent_turn_id,
        iteration_index=None,
        message_index=runtime.message_index,
        assistant_turn_at_ms=runtime.assistant_turn_at_ms,
        model_variant_index=runtime.model_variant_index,
        status=status,
        error_message=error_message,
        completed_at_ms=completed_at_ms,
    )
