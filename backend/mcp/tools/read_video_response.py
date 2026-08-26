"""SoAI - MCP read_video final result dictionary assembly [backend/mcp/tools/read_video_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.read_video_cursor import ReadVideoCursor, encode_cursor
from mcp.tools.read_video_progress_payload import build_read_video_progress_payload

if TYPE_CHECKING:
    from core.read_video.enums import ReadVideoJobStatus
    from core.read_video.records import ReadVideoJobRecord
    from core.types.json import JSONDict
    from mcp.tools.read_video_page import ReadVideoAudioPage, ReadVideoFramePage
    from mcp.tools.read_video_preview import ReadVideoPreviewResult

__all__ = ("build_read_video_result",)


def _source_section(job: ReadVideoJobRecord) -> JSONDict:
    return {
        "source_path": job.source_path,
        "source_mime_type": job.source_mime_type,
        "source_size_bytes": job.source_size_bytes,
        "duration_seconds": job.duration_seconds,
        "source_width": job.source_width,
        "source_height": job.source_height,
        "audio_present": job.audio_present,
    }


def _progress_section(job: ReadVideoJobRecord) -> JSONDict:
    return build_read_video_progress_payload(job)


def _audio_section(
    job: ReadVideoJobRecord,
    audio_page: ReadVideoAudioPage,
    *,
    audio_requested: bool,
    audio_skipped: bool,
) -> JSONDict:
    return {
        "requested": audio_requested,
        "skipped": audio_skipped,
        "present": job.audio_present,
        "transcript": audio_page.transcript_text,
        "segments": list(audio_page.segments),
    }


def _preview_section(preview: ReadVideoPreviewResult | None) -> JSONDict | None:
    if preview is None:
        return None
    return {
        "video_base64": preview.video_base64,
        "content_type": preview.content_type,
        "byte_size": preview.byte_size,
        "width": preview.width,
        "height": preview.height,
        "duration_seconds": preview.duration_seconds,
        "start_seconds": preview.start_seconds,
        "includes_audio": preview.includes_audio,
    }


def _next_cursor(
    job: ReadVideoJobRecord,
    frame_page: ReadVideoFramePage,
    audio_page: ReadVideoAudioPage,
) -> str | None:
    if frame_page.next_frame_offset is None and audio_page.next_segment_offset is None:
        return None
    frame_offset = (
        frame_page.next_frame_offset
        if frame_page.next_frame_offset is not None
        else frame_page.total_frames
    )
    segment_offset = (
        audio_page.next_segment_offset
        if audio_page.next_segment_offset is not None
        else audio_page.total_segments
    )
    return encode_cursor(
        ReadVideoCursor(
            job_id=job.job_id,
            frame_offset=frame_offset,
            segment_offset=segment_offset,
        ),
    )


def build_read_video_result(
    *,
    job: ReadVideoJobRecord,
    status: ReadVideoJobStatus,
    frame_page: ReadVideoFramePage,
    audio_page: ReadVideoAudioPage,
    preview: ReadVideoPreviewResult | None,
    audio_requested: bool,
    audio_skipped: bool,
) -> JSONDict:
    result: JSONDict = {
        "job_id": job.job_id,
        "task_id": job.active_task_id,
        "status": status.value,
        "range_start_seconds": job.range_start_seconds,
        "range_end_seconds": job.range_end_seconds,
        "frames_per_second": job.frames_per_second,
        "include_audio": job.include_audio,
        "progress": _progress_section(job),
        "frames": list(frame_page.frames),
        "audio": _audio_section(
            job,
            audio_page,
            audio_requested=audio_requested,
            audio_skipped=audio_skipped,
        ),
        "video_preview": _preview_section(preview),
        "next_cursor": _next_cursor(job, frame_page, audio_page),
    }
    result.update(_source_section(job))
    return result
