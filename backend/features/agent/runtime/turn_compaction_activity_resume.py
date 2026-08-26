"""SoAI - Auto-compaction activity resume lifecycle [backend/features/agent/runtime/turn_compaction_activity_resume.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_PENDING,
    TOOL_CALL_STATUS_RUNNING,
    normalize_tool_call_status,
)
from features.agent.runtime.turn_compaction_activity_event_builders import (
    build_auto_compaction_started_event,
)
from features.agent.runtime.turn_compaction_activity_projection import (
    persist_auto_compaction_started_activity,
)
from features.agent.runtime.turn_compaction_activity_scope import (
    AutoCompactionActivityScope,
)
from features.agent.runtime.turn_compaction_activity_state import (
    AUTO_COMPACTION_CALL_ID_PREFIX,
    AutoCompactionActivityChronology,
    AutoCompactionActivityState,
    require_auto_compaction_sequence_index,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resume_auto_compaction_activity",)


async def resume_auto_compaction_activity(
    *,
    persisted_activity: JSONDict,
    scope: AutoCompactionActivityScope,
) -> AutoCompactionActivityState:
    call_id_value = persisted_activity.get("call_id")
    call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    if not call_id:
        raise ValidationError("Auto-compaction activity call_id is required.")
    if not call_id.startswith(AUTO_COMPACTION_CALL_ID_PREFIX):
        raise ValidationError("Auto-compaction activity call_id is invalid.")
    tool_name_value = persisted_activity.get("tool_name")
    tool_name = tool_name_value.strip() if isinstance(tool_name_value, str) else ""
    if tool_name != CONTEXT_COMPACTION_TOOL_NAME:
        raise ValidationError("Auto-compaction activity tool_name is invalid.")
    tool_sequence_index = require_auto_compaction_sequence_index(persisted_activity)
    chronology = AutoCompactionActivityChronology.from_activity(persisted_activity)
    status_value = persisted_activity.get("status")
    status = normalize_tool_call_status(status_value if isinstance(status_value, str) else "")
    if status == TOOL_CALL_STATUS_PENDING:
        return await _resume_pending_auto_compaction_activity(
            scope=scope,
            call_id=call_id,
            tool_sequence_index=tool_sequence_index,
            chronology=chronology,
        )
    if status != TOOL_CALL_STATUS_RUNNING:
        raise ValidationError("Auto-compaction activity is not resumable.")
    started_at_ms_value = persisted_activity.get("started_at_ms")
    if (
        isinstance(started_at_ms_value, bool)
        or not isinstance(started_at_ms_value, int)
        or started_at_ms_value <= 0
    ):
        raise ValidationError("Running auto-compaction activity is missing started_at_ms.")
    return AutoCompactionActivityState(
        call_id=call_id,
        sequence_index=tool_sequence_index,
        chronology=chronology,
        started_at_ms=int(started_at_ms_value),
        started_at_monotonic=None,
    )


async def _resume_pending_auto_compaction_activity(
    *,
    scope: AutoCompactionActivityScope,
    call_id: str,
    tool_sequence_index: int,
    chronology: AutoCompactionActivityChronology,
) -> AutoCompactionActivityState:
    started_at_ms = int(epoch_ms())
    started_event = build_auto_compaction_started_event(
        scope=scope,
        call_id=call_id,
        sequence_index=tool_sequence_index,
        chronology=chronology,
        started_at_ms=started_at_ms,
    )
    await uncancel_then_cleanup(
        persist_auto_compaction_started_activity(
            scope=scope,
            event=started_event,
        ),
    )
    return AutoCompactionActivityState(
        call_id=call_id,
        sequence_index=tool_sequence_index,
        chronology=chronology,
        started_at_ms=started_at_ms,
        started_at_monotonic=None,
    )
