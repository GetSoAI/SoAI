"""SoAI - Shared assistant timeline thinking phase emission [backend/features/assistant_timeline/thinking_phase_emission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.conversations.protocols_database_message_streaming import (
    DatabaseStreamingMessagesProtocol,
)
from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.timing.monotonic import monotonic_ms
from core.types.json import JSONDict
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.thinking_phase_state import (
    ThinkingPhaseState,
    clear_active_thinking_phase,
)
from features.assistant_timeline.thinking_phase_upsert import (
    upsert_thinking_phase_from_identity,
)

__all__ = (
    "ThinkingPhaseEmission",
    "ThinkingPhaseEmissionContext",
    "build_thinking_phase_emission",
    "build_thinking_phase_emission_context",
    "build_thinking_phase_emission_context_for_finalize_context",
    "emit_required_thinking_phase",
    "emit_required_thinking_phase_from_parts",
    "emit_thinking_phase",
    "emit_thinking_phase_from_parts",
)


@dataclass(frozen=True, slots=True)
class ThinkingPhaseEmissionContext:
    runtime: AssistantTimelineRuntime
    thinking_phases: list[JSONDict]
    thinking_state: ThinkingPhaseState
    database_messages: DatabaseStreamingMessagesProtocol
    event_bus: EventBusProtocol


def build_thinking_phase_emission_context(
    runtime: AssistantTimelineRuntime,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
) -> ThinkingPhaseEmissionContext:
    return ThinkingPhaseEmissionContext(
        runtime,
        thinking_phases,
        thinking_state,
        database_messages,
        event_bus,
    )


def build_thinking_phase_emission_context_for_finalize_context(
    context: ChatStreamFinalizeContext,
) -> ThinkingPhaseEmissionContext:
    return ThinkingPhaseEmissionContext(
        context.runtime,
        context.thinking_phases,
        context.thinking_state,
        context.database_messages,
        context.event_bus,
    )


@dataclass(frozen=True, slots=True)
class ThinkingPhaseEmission:
    phase_identity: tuple[str, int, str, str | None, int | None, int]
    phase_text: str
    duration_ms: int | None
    status: str
    emitted_at_ms: int | None
    set_active_last_emitted_chars: bool
    clear_active_phase: bool


def build_thinking_phase_emission(
    *,
    phase_identity: tuple[str, int, str, str | None, int | None, int],
    phase_text: str,
    duration_ms: int | None,
    status: str,
    emitted_at_ms: int | None = None,
    set_active_last_emitted_chars: bool = False,
    clear_active_phase: bool = False,
) -> ThinkingPhaseEmission:
    return ThinkingPhaseEmission(
        phase_identity=phase_identity,
        phase_text=phase_text,
        duration_ms=duration_ms,
        status=status,
        emitted_at_ms=emitted_at_ms,
        set_active_last_emitted_chars=set_active_last_emitted_chars,
        clear_active_phase=clear_active_phase,
    )


async def emit_thinking_phase(
    *,
    context: ThinkingPhaseEmissionContext,
    emission: ThinkingPhaseEmission,
) -> bool:
    phase_emitted = await upsert_thinking_phase_from_identity(
        runtime=context.runtime,
        thinking_phases=context.thinking_phases,
        thinking_state=context.thinking_state,
        database_messages=context.database_messages,
        event_bus=context.event_bus,
        phase_identity=emission.phase_identity,
        phase_text=emission.phase_text,
        status=emission.status,
    )
    if phase_emitted:
        now_ms = emission.emitted_at_ms if emission.emitted_at_ms is not None else monotonic_ms()
        context.thinking_state.last_emit_ms = now_ms
        if emission.set_active_last_emitted_chars:
            context.thinking_state.active_last_emitted_chars = len(emission.phase_text)
    if emission.clear_active_phase:
        clear_active_thinking_phase(context.thinking_state)
    return phase_emitted


async def emit_thinking_phase_from_parts(
    *,
    runtime: AssistantTimelineRuntime,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    emission: ThinkingPhaseEmission,
) -> bool:
    return await emit_thinking_phase(
        context=build_thinking_phase_emission_context(
            runtime,
            thinking_phases,
            thinking_state,
            database_messages,
            event_bus,
        ),
        emission=emission,
    )


async def emit_required_thinking_phase(
    *,
    context: ThinkingPhaseEmissionContext,
    emission: ThinkingPhaseEmission,
    error_message: str,
) -> None:
    phase_emitted = await emit_thinking_phase(context=context, emission=emission)
    if not phase_emitted:
        raise ValidationError(error_message)


async def emit_required_thinking_phase_from_parts(
    *,
    runtime: AssistantTimelineRuntime,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    emission: ThinkingPhaseEmission,
    error_message: str,
) -> None:
    phase_emitted = await emit_thinking_phase_from_parts(
        runtime=runtime,
        thinking_phases=thinking_phases,
        thinking_state=thinking_state,
        database_messages=database_messages,
        event_bus=event_bus,
        emission=emission,
    )
    if not phase_emitted:
        raise ValidationError(error_message)
