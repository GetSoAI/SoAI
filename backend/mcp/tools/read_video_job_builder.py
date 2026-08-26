"""SoAI - MCP read_video new durable job record construction [backend/mcp/tools/read_video_job_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.read_video.enums import ReadVideoJobStatus
from core.read_video.records import ReadVideoJobRecord

if TYPE_CHECKING:
    from core.media.types import VideoProbeResult
    from core.read_video.records import ReadVideoSourceSignature
    from mcp.tools.read_video_config import ReadVideoConfig
    from mcp.tools.read_video_range import ReadVideoResolvedRange

__all__ = ("build_new_job_record",)

_MS_PER_HOUR = 3_600_000


def build_new_job_record(
    *,
    probe: VideoProbeResult,
    resolved_range: ReadVideoResolvedRange,
    config: ReadVideoConfig,
    resolved_path: str,
    owner_key: str,
    user_id: str | None,
    conversation_id: str | None,
    active_task_id: str | None,
    active_tool_call_id: str | None,
    include_audio: bool,
    source_size_bytes: int,
    now_ms: int,
    job_id: str,
    job_key: str,
    config_signature: str,
    source_signature: ReadVideoSourceSignature,
    page_size: int,
) -> ReadVideoJobRecord:
    return ReadVideoJobRecord(
        job_id=job_id,
        job_key=job_key,
        owner_key=owner_key,
        user_id=user_id,
        conversation_id=conversation_id,
        active_task_id=active_task_id,
        active_tool_call_id=active_tool_call_id,
        source_path=resolved_path,
        source_signature=source_signature,
        source_size_bytes=source_size_bytes,
        source_mime_type=probe.mime_type,
        duration_seconds=probe.duration_seconds,
        source_width=probe.width,
        source_height=probe.height,
        audio_present=probe.audio_present,
        range_start_seconds=resolved_range.range_start_seconds,
        range_end_seconds=resolved_range.range_end_seconds,
        frames_per_second=resolved_range.frames_per_second,
        include_audio=include_audio,
        config_signature=config_signature,
        status=ReadVideoJobStatus.PENDING,
        progress_stage=None,
        percent_complete=0.0,
        frames_done=0,
        frames_total_estimate=None,
        audio_chunks_done=0,
        audio_chunks_total_estimate=None,
        current_timestamp_seconds=None,
        page_size=page_size,
        lease_token=None,
        lease_owner=None,
        lease_expires_at_ms=None,
        error_code=None,
        error_message=None,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
        expires_at_ms=now_ms + config.job_retention_hours * _MS_PER_HOUR,
    )
