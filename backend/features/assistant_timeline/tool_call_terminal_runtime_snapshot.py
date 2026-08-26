"""SoAI - Terminal tool-call runtime snapshot resolution [backend/features/assistant_timeline/tool_call_terminal_runtime_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from features.assistant_timeline.tool_call_terminal_payload import (
    resolve_pending_terminal_call_ids,
)

if TYPE_CHECKING:
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "TerminalToolCallRuntimeSnapshot",
    "resolve_terminal_tool_call_runtime_snapshot",
)


@dataclass(frozen=True, slots=True)
class TerminalToolCallRuntimeSnapshot:
    pending_call_ids: list[str]
    pending_subagent_call_ids: set[str]


def _collect_pending_subagent_call_ids(runtime: AssistantTimelineRuntime) -> set[str]:
    pending_subagent_call_ids: set[str] = set()
    pending_tool_events = runtime.pending_tool_events
    if pending_tool_events is not None:
        for pending_event in pending_tool_events:
            pending_payload = pending_event.tool_payload
            pending_tool_name_value = pending_payload.get("tool_name")
            pending_tool_name = (
                pending_tool_name_value.strip() if isinstance(pending_tool_name_value, str) else ""
            )
            if pending_tool_name != "subagent_spawn":
                continue
            pending_call_id_value = pending_payload.get("call_id")
            pending_call_id = (
                pending_call_id_value.strip() if isinstance(pending_call_id_value, str) else ""
            )
            if pending_call_id:
                pending_subagent_call_ids.add(pending_call_id)
    for call_id, tool_name in runtime.tool_name_by_call_id.items():
        if isinstance(tool_name, str) and tool_name.strip() == "subagent_spawn" and call_id.strip():
            pending_subagent_call_ids.add(call_id.strip())
    return pending_subagent_call_ids


def _resolve_layout_sequence_index(runtime: AssistantTimelineRuntime, call_id: str) -> int:
    layout = runtime.tool_call_layout_by_call_id.get(call_id)
    if layout is not None:
        return layout.sequence_index
    pending_tool_events = runtime.pending_tool_events
    if pending_tool_events is None:
        return 1_000_000_000
    for pending_event in pending_tool_events:
        pending_call_id_value = pending_event.tool_payload.get("call_id")
        pending_call_id = (
            pending_call_id_value.strip() if isinstance(pending_call_id_value, str) else ""
        )
        if pending_call_id == call_id:
            return int(pending_event.sequence_index)
    return 1_000_000_000


def resolve_terminal_tool_call_runtime_snapshot(
    runtime: AssistantTimelineRuntime,
) -> TerminalToolCallRuntimeSnapshot:
    pending_call_ids = resolve_pending_terminal_call_ids(runtime)
    pending_call_ids.sort(
        key=lambda call_id: (_resolve_layout_sequence_index(runtime, call_id), call_id),
    )
    return TerminalToolCallRuntimeSnapshot(
        pending_call_ids=pending_call_ids,
        pending_subagent_call_ids=_collect_pending_subagent_call_ids(runtime),
    )
