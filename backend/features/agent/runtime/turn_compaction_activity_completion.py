"""SoAI - Auto-compaction terminal persistence and event publication [backend/features/agent/runtime/turn_compaction_activity_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.timing.epoch import epoch_ms
from core.tool_calls.visibility import should_persist_visible_tool_call_rows
from features.agent.runtime.context_compaction.activity_result import (
    AutoCompactionActivityMetadata,
    build_auto_compaction_result_payload,
)
from features.agent.runtime.context_compaction.tool_projection_persistence import (
    persist_context_compaction_completed_projection,
)
from features.agent.runtime.turn_compaction_activity_event_builders import (
    build_auto_compaction_completed_event,
)
from features.agent.runtime.turn_compaction_activity_scope import (
    AutoCompactionActivityScope,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.agent.runtime.turn_compaction_activity_state import (
        AutoCompactionActivityChronology,
        AutoCompactionActivityState,
    )

__all__ = (
    "complete_auto_compaction_activity",
    "complete_started_auto_compaction_activity",
)


async def complete_auto_compaction_activity(
    *,
    activity: AutoCompactionActivityState,
    scope: AutoCompactionActivityScope,
    status: str,
    output_text: str,
    prompt_message: JSONDict | None,
    error_message: str | None,
    metadata: AutoCompactionActivityMetadata | None,
) -> None:
    if activity.started_at_monotonic is not None:
        duration_ms = max(
            0,
            int((time.monotonic() - activity.started_at_monotonic) * 1000),
        )
    else:
        duration_ms = max(0, int(epoch_ms()) - int(activity.started_at_ms))
    result_payload = build_auto_compaction_result_payload(
        status=status,
        output_text=output_text,
        prompt_message=prompt_message,
        error_message=error_message,
        metadata=metadata,
    )
    completed_at_ms = int(epoch_ms())
    await uncancel_then_cleanup(
        _persist_completed_projection_and_activity(
            scope=scope,
            call_id=activity.call_id,
            sequence_index=activity.sequence_index,
            chronology=activity.chronology,
            status=status,
            result_payload=result_payload,
            duration_ms=duration_ms,
            error_message=error_message,
            completed_at_ms=completed_at_ms,
        ),
    )


async def complete_started_auto_compaction_activity(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    tool_sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    status: str,
    output_text: str,
    error_message: str,
    duration_ms: int,
    persist_activity: bool,
) -> None:
    result_payload = build_auto_compaction_result_payload(
        status=status,
        output_text=output_text,
        prompt_message=None,
        error_message=error_message,
        metadata=None,
    )
    await uncancel_then_cleanup(
        _persist_completed_projection_and_activity(
            scope=scope,
            call_id=call_id,
            sequence_index=tool_sequence_index,
            chronology=chronology,
            status=status,
            result_payload=result_payload,
            duration_ms=duration_ms,
            error_message=error_message,
            completed_at_ms=int(epoch_ms()),
            persist_activity=persist_activity,
        ),
    )


async def _persist_completed_projection_and_activity(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    status: str,
    result_payload: JSONDict,
    duration_ms: int,
    error_message: str | None,
    completed_at_ms: int,
    persist_activity: bool = True,
) -> None:
    if should_persist_visible_tool_call_rows(scope.request_context):
        await persist_context_compaction_completed_projection(
            database_tool_calls=scope.database_tool_calls,
            request_context=scope.request_context,
            tool_context=scope.tool_context,
            call_id=call_id,
            status=status,
            result_payload=result_payload,
            duration_ms=duration_ms,
            error_message=error_message,
            completed_at_ms=completed_at_ms,
        )
    if not persist_activity:
        return
    await _persist_completed_activity(
        scope=scope,
        call_id=call_id,
        sequence_index=sequence_index,
        chronology=chronology,
        status=status,
        result_payload=result_payload,
        duration_ms=duration_ms,
        error_message=error_message,
    )


async def _persist_completed_activity(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    sequence_index: int,
    chronology: AutoCompactionActivityChronology,
    status: str,
    result_payload: JSONDict,
    duration_ms: int,
    error_message: str | None,
) -> None:
    completed_sequence = int(await scope.next_action_sequence())
    completed_event = build_auto_compaction_completed_event(
        scope=scope,
        call_id=call_id,
        sequence_index=sequence_index,
        chronology=chronology,
        status=status,
        result=result_payload,
        duration_ms=duration_ms,
        error_message=error_message,
    )
    await scope.turn_state_writer.persist_tool_activity(
        event=completed_event,
        activity_sequence=completed_sequence,
        text_length_before=chronology.content_index_before,
    )
    await scope.publish_event(completed_event)
