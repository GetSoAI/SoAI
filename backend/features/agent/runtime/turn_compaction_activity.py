"""SoAI - Auto-compaction synthetic tool activity lifecycle [backend/features/agent/runtime/turn_compaction_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.agent.turn_state_writer import TurnStateWriter
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.epoch import epoch_ms
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_ERROR,
)
from features.agent.runtime.turn_compaction_activity_completion import (
    complete_started_auto_compaction_activity,
)
from features.agent.runtime.turn_compaction_activity_event_builders import (
    build_auto_compaction_created_event,
    build_auto_compaction_started_event,
)
from features.agent.runtime.turn_compaction_activity_projection import (
    persist_auto_compaction_pending_projection,
    persist_auto_compaction_started_activity,
)
from features.agent.runtime.turn_compaction_activity_scope import (
    AutoCompactionActivityScope,
)
from features.agent.runtime.turn_compaction_activity_state import (
    AutoCompactionActivityState,
    build_auto_compaction_call_id,
)

if TYPE_CHECKING:
    from core.events.types_conversation import (
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )
    from features.agent.runtime.turn_compaction_activity_state import (
        AutoCompactionActivityChronology,
    )
    from features.agent.runtime.turn_loop_tool_sequences import (
        TurnLoopToolSequenceState,
    )

__all__ = ("start_auto_compaction_activity",)


async def _persist_tool_activity(
    *,
    event: ToolCallCreatedEvent | ToolCallStartedEvent,
    activity_sequence: int,
    content_index_before: int,
    turn_state_writer: TurnStateWriter,
) -> None:
    await turn_state_writer.persist_tool_activity(
        event=event,
        activity_sequence=activity_sequence,
        text_length_before=content_index_before,
    )


async def start_auto_compaction_activity(
    *,
    scope: AutoCompactionActivityScope,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    tool_sequence_state: TurnLoopToolSequenceState,
) -> AutoCompactionActivityState:
    if (
        isinstance(sequence_index, bool)
        or not isinstance(sequence_index, int)
        or sequence_index < 0
    ):
        raise ValidationError("Auto-compaction activity sequence_index is required.")
    if tool_sequence_state.next_sequence_index != int(sequence_index) + 1:
        raise ValidationError(
            "Auto-compaction activity sequence_index was not reserved by the shared tool sequence allocator.",
        )
    created_sequence = int(await scope.next_action_sequence())
    call_id = build_auto_compaction_call_id(
        turn_id=scope.turn_id,
        iteration_index=scope.iteration_index,
        created_sequence=created_sequence,
    )
    created_at_ms = int(epoch_ms())
    projection_persisted = False
    created_activity_persisted = False
    started_at_ms = int(created_at_ms)
    try:
        projection_persisted = await persist_auto_compaction_pending_projection(
            scope=scope,
            call_id=call_id,
            sequence_index=sequence_index,
            chronology=chronology,
            created_at_ms=created_at_ms,
        )
        created_event = build_auto_compaction_created_event(
            scope=scope,
            call_id=call_id,
            sequence_index=sequence_index,
            chronology=chronology,
        )
        await _persist_tool_activity(
            event=created_event,
            activity_sequence=created_sequence,
            content_index_before=chronology.content_index_before,
            turn_state_writer=scope.turn_state_writer,
        )
        created_activity_persisted = True
        await scope.publish_event(created_event)
        started_at_ms = int(epoch_ms())
        started_event = build_auto_compaction_started_event(
            scope=scope,
            call_id=call_id,
            sequence_index=sequence_index,
            chronology=chronology,
            started_at_ms=started_at_ms,
        )
        await persist_auto_compaction_started_activity(
            scope=scope,
            event=started_event,
        )
    except asyncio.CancelledError:
        if projection_persisted or created_activity_persisted:
            await uncancel_then_cleanup(
                _complete_interrupted_start_activity(
                    scope=scope,
                    call_id=call_id,
                    sequence_index=sequence_index,
                    chronology=chronology,
                    status=TOOL_CALL_STATUS_CANCELLED,
                    output_text="Context compaction cancelled.",
                    error_message="Context compaction cancelled.",
                    persist_activity=created_activity_persisted,
                ),
            )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        if projection_persisted or created_activity_persisted:
            await uncancel_then_cleanup(
                _complete_interrupted_start_activity(
                    scope=scope,
                    call_id=call_id,
                    sequence_index=sequence_index,
                    chronology=chronology,
                    status=TOOL_CALL_STATUS_ERROR,
                    output_text="Context compaction failed.",
                    error_message="Context compaction failed.",
                    persist_activity=created_activity_persisted,
                ),
            )
        raise
    return AutoCompactionActivityState(
        call_id=call_id,
        sequence_index=sequence_index,
        chronology=chronology,
        started_at_ms=started_at_ms,
        started_at_monotonic=time.monotonic(),
    )


async def _complete_interrupted_start_activity(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    status: str,
    output_text: str,
    error_message: str,
    persist_activity: bool,
) -> None:
    await complete_started_auto_compaction_activity(
        scope=scope,
        call_id=call_id,
        tool_sequence_index=sequence_index,
        chronology=chronology,
        status=status,
        output_text=output_text,
        error_message=error_message,
        duration_ms=0,
        persist_activity=persist_activity,
    )
