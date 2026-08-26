"""SoAI - Agent turn snapshot serialization helpers [backend/core/agent/turn_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.execution.protocols import AgentTurnSnapshot
from core.execution.serialization import serialize_owned_execution_core

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("serialize_agent_turn_snapshot",)


def serialize_agent_turn_snapshot(snapshot: AgentTurnSnapshot) -> JSONDict:
    payload = serialize_owned_execution_core(snapshot)
    payload.update(
        {
            "conv_id": snapshot.conv_id,
            "user_id": snapshot.user_id,
            "turn_id": snapshot.turn_id,
            "turn_scope": snapshot.turn_scope,
            "parent_turn_id": snapshot.parent_turn_id,
            "parent_tool_call_id": snapshot.parent_tool_call_id,
            "parent_iteration_index": snapshot.parent_iteration_index,
            "display_name": snapshot.display_name,
            "requested_model": snapshot.requested_model,
            "owner_task_id": snapshot.owner_task_id,
            "execution_token": snapshot.execution_token,
            "server_boot_id": snapshot.server_boot_id,
            "mode": snapshot.mode,
            "max_iterations": snapshot.max_iterations,
            "iteration_index": snapshot.iteration_index,
            "sequence": snapshot.sequence,
            "turn_cancellation_id": snapshot.turn_cancellation_id,
            "active_inference_cancellation_id": snapshot.active_inference_cancellation_id,
            "assistant_text": snapshot.assistant_text,
            "tool_calls": snapshot.tool_calls,
            "tool_results": snapshot.tool_results,
            "activities": snapshot.activities,
            "reached_max_iterations": snapshot.reached_max_iterations,
            "error_message": snapshot.error_message,
            "error_type": snapshot.error_type,
            "todo_revision": snapshot.todo_revision,
            "todo_explanation": snapshot.todo_explanation,
            "todo": snapshot.todo,
        },
    )
    return payload
