"""SoAI - Assistant timeline pending tool output delta draining [backend/features/assistant_timeline/tool_output_delta_drain.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.tool_output_limits import append_capped_tool_output

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "ToolOutputDeltaDrainResult",
    "drain_pending_tool_output_deltas_locked",
)


@dataclass(frozen=True, slots=True)
class ToolOutputDeltaDrainResult:
    tool_result: JSONDict
    has_output: bool


def drain_pending_tool_output_deltas_locked(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
) -> ToolOutputDeltaDrainResult | None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return None
    pending = runtime.pending_tool_output_deltas_by_call_id.get(normalized_call_id)
    if not pending:
        return None
    accumulated_output = runtime.tool_output_by_call_id.get(normalized_call_id, "")
    has_output = False
    for delta in pending:
        if not delta:
            continue
        accumulated_output = append_capped_tool_output(accumulated_output, delta)
        has_output = True
    runtime.pending_tool_output_deltas_by_call_id.pop(normalized_call_id, None)
    if has_output:
        runtime.tool_output_by_call_id[normalized_call_id] = accumulated_output
    runtime.tool_output_delta_last_flush_monotonic_ms_by_call_id[normalized_call_id] = int(
        monotonic_ms(),
    )
    return ToolOutputDeltaDrainResult(
        tool_result={"output": accumulated_output},
        has_output=has_output,
    )
