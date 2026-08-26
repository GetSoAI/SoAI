"""SoAI - MCP read_video task progress and live activity updates [backend/mcp/tools/read_video_task_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.status_transitions import update_progress
from core.tool_calls.live_update_identity import ToolCallLiveUpdateIdentity
from core.tool_calls.live_update_publishing import publish_tool_call_live_update

if TYPE_CHECKING:
    from core.read_video.operations import ReadVideoProgressUpdate
    from core.runtime.request_context import RequestContext
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("publish_read_video_progress",)


def _progress_payload(progress: ReadVideoProgressUpdate, *, task_id: str | None) -> JSONDict:
    return {
        "job_id": progress.job_id,
        "task_id": task_id,
        "status": "running",
        "progress": {
            "stage": progress.stage,
            "percent_complete": progress.percent_complete,
            "frames_done": progress.frames_done,
            "frames_total_estimate": progress.frames_total_estimate,
            "audio_chunks_done": progress.audio_chunks_done,
            "audio_chunks_total_estimate": progress.audio_chunks_total_estimate,
            "current_timestamp_seconds": progress.current_timestamp_seconds,
        },
    }


def _tool_payload(
    identity: CurrentToolCallIdentity,
    progress: ReadVideoProgressUpdate,
    *,
    task_id: str | None,
) -> JSONDict:
    return {
        "call_id": identity.call_id,
        "tool_name": "read_video",
        "status": "running",
        "message_index": identity.message_index,
        "assistant_turn_at_ms": identity.assistant_turn_at_ms,
        "model_variant_index": identity.model_variant_index,
        "sequence_index": identity.sequence_index,
        "content_index_before": identity.content_index_before,
        "thinking_index_before": identity.thinking_index_before,
        "result": _progress_payload(progress, task_id=task_id),
        "collapsed": False,
    }


def _live_identity(
    identity: CurrentToolCallIdentity,
    request_context: RequestContext | None,
) -> ToolCallLiveUpdateIdentity:
    request_id = request_context.trace_id if request_context is not None else None
    return ToolCallLiveUpdateIdentity(
        user_id=identity.user_id,
        conv_id=identity.conv_id,
        request_id=request_id,
        assistant_at_ms=identity.assistant_at_ms,
        assistant_turn_at_ms=identity.assistant_turn_at_ms,
        model_variant_index=identity.model_variant_index,
    )


async def publish_read_video_progress(
    utility_tools: MCPUtilityToolsProtocol,
    progress: ReadVideoProgressUpdate,
    *,
    task_id: str | None,
) -> None:
    if task_id is not None:
        await update_progress(
            utility_tools.task_registry,
            task_id,
            progress.frames_done + progress.audio_chunks_done,
            status_message=progress.stage,
            details=_progress_payload(progress, task_id=task_id),
            percent_override=round(progress.percent_complete),
        )
    identity = utility_tools.active_tool_call_context.get(None)
    if identity is None:
        return
    request_context = utility_tools.active_request_context.get(None)
    payload = _progress_payload(progress, task_id=task_id)
    await publish_tool_call_live_update(
        event_bus=utility_tools.event_bus,
        database_tool_calls=utility_tools.database_tool_calls,
        identity=_live_identity(identity, request_context),
        call_id=identity.call_id,
        event_type="tool_call_updated",
        tool_payload=_tool_payload(identity, progress, task_id=task_id),
        status="running",
        duration_ms=None,
        started_at_ms=None,
        tool_result=payload,
    )
