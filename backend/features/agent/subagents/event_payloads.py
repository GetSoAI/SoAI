"""SoAI - Subagent event payload normalization [backend/features/agent/subagents/event_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.execution.protocols import SubagentSnapshot
from core.types.json import JSONDict
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import (
    coerce_optional_non_negative_int_strict,
    require_non_negative_int_strict,
)
from features.agent.events.subagent_types import SubagentEventBase
from features.agent.subagents.event_payload_factories import (
    build_subagent_running_event,
    build_subagent_terminal_event,
)

__all__ = (
    "SubagentEventPayload",
    "build_subagent_event_payload",
    "build_subagent_running_event",
    "build_subagent_terminal_event",
    "read_snapshot_text",
)


@dataclass(kw_only=True, slots=True)
class SubagentEventPayload(SubagentEventBase):
    status: str


def build_subagent_event_payload(
    *,
    snapshot: SubagentSnapshot,
    user_id: int,
    conv_id: str,
    result_text: str | None,
    error_message: str | None,
    token_usage: JSONDict | None,
    updated_at_ms_override: int | None = None,
) -> SubagentEventPayload:
    snapshot_updated_at_ms = require_non_negative_int_strict(
        snapshot.updated_at_ms,
        error_message="Subagent event publication requires a non-negative integer.",
    )
    if updated_at_ms_override is None:
        resolved_updated_at_ms = snapshot_updated_at_ms
    else:
        override_value = require_unix_epoch_ms(
            updated_at_ms_override,
            error_message="Subagent event publication requires updated_at_ms_override in epoch ms.",
            enforce_maximum=False,
        )
        resolved_updated_at_ms = max(snapshot_updated_at_ms, override_value)
    return SubagentEventPayload(
        user_id=user_id,
        conv_id=conv_id,
        status=snapshot.status,
        parent_turn_id=snapshot.parent_turn_id,
        parent_tool_call_id=snapshot.parent_tool_call_id,
        parent_iteration_index=require_non_negative_int_strict(
            snapshot.parent_iteration_index,
            error_message="Subagent event publication requires a non-negative integer.",
        ),
        subagent_id=snapshot.subagent_id,
        execution_type=snapshot.execution_type,
        display_name=snapshot.display_name,
        mode=snapshot.mode,
        owner_task_id=snapshot.owner_task_id,
        status_message=snapshot.status_message,
        started_at_ms=require_non_negative_int_strict(
            snapshot.started_at_ms,
            error_message="Subagent event publication requires a non-negative integer.",
        ),
        updated_at_ms=resolved_updated_at_ms,
        finished_at_ms=coerce_optional_non_negative_int_strict(snapshot.finished_at_ms),
        requested_model=snapshot.requested_model,
        result_text=result_text,
        error_message=error_message,
        error_type=snapshot.error_type,
        token_usage=token_usage,
    )


def read_snapshot_text(value: str | None) -> str | None:
    return value
