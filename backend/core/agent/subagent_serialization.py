"""SoAI - Subagent contract serialization and schema helpers [backend/core/agent/subagent_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.protocols import SubagentAcceptedExecution, SubagentCancelResult
from core.execution.protocols import SubagentSnapshot
from core.execution.serialization import serialize_owned_execution_core
from core.validation.epoch import EPOCH_MS_MIN

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_subagent_accepted_execution_json_schema",
    "build_subagent_snapshot_json_schema",
    "serialize_subagent_accepted_execution",
    "serialize_subagent_cancel_result",
    "serialize_subagent_snapshot",
    "serialize_subagent_snapshots",
)


def serialize_subagent_accepted_execution(
    execution: SubagentAcceptedExecution,
) -> JSONDict:
    return {
        "subagent_id": execution.subagent_id,
        "owner_task_id": execution.owner_task_id,
        "status": execution.status,
        "mode": execution.mode,
        "conv_id": execution.conv_id,
        "requested_model": execution.requested_model,
    }


def serialize_subagent_snapshot(snapshot: SubagentSnapshot | None) -> JSONDict | None:
    if snapshot is None:
        return None
    payload = serialize_owned_execution_core(snapshot)
    payload.update(
        {
            "subagent_id": snapshot.subagent_id,
            "mode": snapshot.mode,
            "display_name": snapshot.display_name,
            "conv_id": snapshot.conv_id,
            "parent_turn_id": snapshot.parent_turn_id,
            "parent_tool_call_id": snapshot.parent_tool_call_id,
            "parent_iteration_index": snapshot.parent_iteration_index,
            "result_text": snapshot.result_text,
            "error_message": snapshot.error_message,
            "error_type": snapshot.error_type,
        },
    )
    return payload


def serialize_subagent_snapshots(snapshots: list[SubagentSnapshot]) -> list[JSONDict]:
    serialized_snapshots: list[JSONDict] = []
    for snapshot in snapshots:
        serialized = serialize_subagent_snapshot(snapshot)
        if serialized is not None:
            serialized_snapshots.append(serialized)
    return serialized_snapshots


def serialize_subagent_cancel_result(result: SubagentCancelResult) -> JSONDict:
    return {"cancelled": result.cancelled}


def build_subagent_snapshot_json_schema(
    *,
    statuses: tuple[str, ...],
    modes: tuple[str, ...],
) -> JSONDict:
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": {
            "subagent_id": {"type": "string"},
            "execution_type": {"type": "string"},
            "owner_task_id": {"type": ["string", "null"]},
            "status": {"type": "string", "enum": list(statuses)},
            "status_message": {"type": ["string", "null"]},
            "mode": {"type": "string", "enum": list(modes)},
            "display_name": {"type": ["string", "null"]},
            "conv_id": {"type": "string"},
            "parent_turn_id": {"type": "string"},
            "parent_tool_call_id": {"type": "string"},
            "parent_iteration_index": {"type": "integer", "minimum": 0},
            "started_at_ms": {"type": "integer", "minimum": EPOCH_MS_MIN},
            "updated_at_ms": {"type": "integer", "minimum": EPOCH_MS_MIN},
            "finished_at_ms": {"type": ["integer", "null"], "minimum": EPOCH_MS_MIN},
            "requested_model": {"type": ["string", "null"]},
            "result_text": {"type": ["string", "null"]},
            "error_message": {"type": ["string", "null"]},
            "error_type": {"type": ["string", "null"]},
            "token_usage": {"type": ["object", "null"], "additionalProperties": True},
        },
        "required": [
            "subagent_id",
            "execution_type",
            "owner_task_id",
            "status",
            "status_message",
            "mode",
            "display_name",
            "conv_id",
            "parent_turn_id",
            "parent_tool_call_id",
            "parent_iteration_index",
            "started_at_ms",
            "updated_at_ms",
            "finished_at_ms",
            "requested_model",
            "result_text",
            "error_message",
            "error_type",
            "token_usage",
        ],
    }


def build_subagent_accepted_execution_json_schema(
    *,
    accepted_statuses: tuple[str, ...],
    modes: tuple[str, ...],
) -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "subagent_id": {"type": "string"},
            "owner_task_id": {"type": "string"},
            "status": {"type": "string", "enum": list(accepted_statuses)},
            "mode": {"type": "string", "enum": list(modes)},
            "conv_id": {"type": "string"},
            "requested_model": {"type": ["string", "null"]},
        },
        "required": [
            "subagent_id",
            "owner_task_id",
            "status",
            "mode",
            "conv_id",
            "requested_model",
        ],
    }
