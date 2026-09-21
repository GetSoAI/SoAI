"""SoAI - Interrupted manual compaction process-boundary recovery [backend/database/repositories/users/manual_compaction_process_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.agent.turn_record_fields import read_turn_optional_text
from core.database.requests import (
    ManualCompactionAssistantEventRequest,
    ManualCompactionTerminalCommitRequest,
)
from core.serialization.json_parsing import parse_json_dict
from core.tool_calls.context_compaction_events import (
    build_context_compaction_tool_call_completed_event,
)
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_TOOL_NAME,
    build_manual_context_compaction_call_id,
)
from core.tool_calls.context_compaction_result import (
    build_context_compaction_result_payload,
)
from core.tool_calls.status_values import TOOL_CALL_STATUS_CANCELLED
from core.tool_calls.tool_event_payloads import map_tool_call_event_to_tool_payload
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from database.repositories.users.manual_compaction_terminal_commit import (
    sync_commit_manual_compaction_terminal,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_recover_interrupted_manual_compaction",)

RECOVERY_MESSAGE = "Manual compaction was interrupted by a process boundary."


def _resolve_started_tool(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    turn_id: str,
) -> tuple[int, str, int] | None:
    rows = conn.execute(
        """
        SELECT event.assistant_at_ms, event.payload_json, message.finalized_at_ms
        FROM webui_assistant_message_events AS event
        JOIN webui_messages AS message
          ON message.conv_id = event.conv_id
         AND message.created_at_ms = event.assistant_at_ms
         AND message.assistant_turn_at_ms = event.assistant_at_ms
         AND message.model_variant_index = 0
         AND message.role = 'assistant'
        WHERE event.conv_id = ? AND event.event_type = 'tool_call_started'
          AND message.finalized_at_ms IS NULL
        ORDER BY event.assistant_at_ms DESC, event.sequence DESC
        """,
        (conv_id,),
    ).fetchall()
    for assistant_at_ms, payload_json, _ in rows:
        if not is_strict_int(assistant_at_ms) or not isinstance(payload_json, str):
            continue
        payload = parse_json_dict(payload_json, field="manual compaction start event")
        tool = coerce_json_dict(payload.get("tool"))
        if (
            tool is None
            or tool.get("tool_name") != CONTEXT_COMPACTION_TOOL_NAME
            or tool.get("turn_id") != turn_id
        ):
            continue
        call_id = tool.get("call_id")
        started_at_ms = tool.get("started_at_ms")
        if (
            isinstance(call_id, str)
            and call_id == build_manual_context_compaction_call_id(turn_id)
            and is_strict_int(started_at_ms)
        ):
            return int(assistant_at_ms), call_id, int(started_at_ms)
    return None


def sync_recover_interrupted_manual_compaction(
    conn: sqlite3.Connection,
    *,
    turn_record: JSONDict,
    completed_at_ms: int,
) -> bool:
    conv_id = str(turn_record.get("conv_id") or "").strip()
    turn_id = str(turn_record.get("turn_id") or "").strip()
    execution_token = str(turn_record.get("execution_token") or "").strip()
    user_id = turn_record.get("user_id")
    iteration_index = turn_record.get("iteration_index")
    if not conv_id or not turn_id or not execution_token:
        return False
    if not is_strict_int(user_id) or not is_strict_int(iteration_index):
        return False
    started_tool = _resolve_started_tool(conn, conv_id=conv_id, turn_id=turn_id)
    if started_tool is None:
        return False
    assistant_at_ms, tool_call_id, started_at_ms = started_tool
    model_value = turn_record.get("requested_model")
    model_id = model_value.strip() if isinstance(model_value, str) and model_value.strip() else None
    result_payload = build_context_compaction_result_payload(
        status=TOOL_CALL_STATUS_CANCELLED,
        output_text="Context compaction was interrupted.",
        prompt_message=None,
        error_message=RECOVERY_MESSAGE,
        compaction_details={"trigger": "manual", "model": model_id},
        default_error_message=RECOVERY_MESSAGE,
    )
    duration_ms = max(0, int(completed_at_ms) - started_at_ms)
    terminal_tool_event = build_context_compaction_tool_call_completed_event(
        user_id=int(user_id),
        conv_id=conv_id,
        call_id=tool_call_id,
        message_index=0,
        sequence_index=0,
        content_index_before=0,
        thinking_index_before=0,
        thinking_duration_before_ms=None,
        status=TOOL_CALL_STATUS_CANCELLED,
        result=result_payload,
        duration_ms=duration_ms,
        error_message=RECOVERY_MESSAGE,
        turn_id=turn_id,
        iteration_index=int(iteration_index),
    )
    sync_commit_manual_compaction_terminal(
        conn,
        ManualCompactionTerminalCommitRequest(
            conv_id=conv_id,
            user_id=int(user_id),
            turn_id=turn_id,
            execution_token=execution_token,
            iteration_index=int(iteration_index),
            tool_call_id=tool_call_id,
            tool_started_at_ms=started_at_ms,
            completed_at_ms=int(completed_at_ms),
            model_id=model_id,
            assistant_at_ms=assistant_at_ms,
            finish_reason="cancelled",
            terminal_status=TOOL_CALL_STATUS_CANCELLED,
            error_message=RECOVERY_MESSAGE,
            error_type="process_boundary_interrupted",
            turn_cancellation_id=read_turn_optional_text(turn_record, "turn_cancellation_id"),
            result_payload=result_payload,
            terminal_event=ManualCompactionAssistantEventRequest(
                sequence=2,
                assistant_revision=3,
                event_type="tool_call_completed",
                tool_payload=map_tool_call_event_to_tool_payload(terminal_tool_event),
                created_at_ms=int(completed_at_ms),
            ),
            replace_assistant_at_ms=None,
            replace_tool_call_id=None,
        ),
    )
    return True
