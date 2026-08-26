"""SoAI - Assistant timeline status preview phase resolution [backend/features/assistant_timeline/status_preview_phase.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("resolve_status_preview_phase",)


def _has_running_context_compaction(runtime: AssistantTimelineRuntime) -> bool:
    for call_id in runtime.running_tool_call_ids:
        tool_name = runtime.tool_name_by_call_id.get(call_id)
        if tool_name == CONTEXT_COMPACTION_TOOL_NAME:
            return True
    return False


def resolve_status_preview_phase(runtime: AssistantTimelineRuntime) -> str:
    if runtime.wait_for_user_activity.status == "running":
        return "waiting_for_user"
    if _has_running_context_compaction(runtime):
        return "context_compaction"
    if runtime.running_tool_call_ids:
        return "running_tool"
    thinking_phases = runtime.thinking_phases
    if thinking_phases:
        latest_phase = thinking_phases[-1]
        if isinstance(latest_phase, dict) and latest_phase.get("status") == "running":
            return "thinking"
    if runtime.processing_activity.status == "running":
        return "processing"
    if runtime.loading_activity.status == "running":
        return "loading"
    if runtime.assistant_visible_chars > 0:
        return "responding"
    return "working"
