"""SoAI - Shared read_video progress payload assembly [backend/mcp/tools/read_video_progress_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.read_video.records import ReadVideoJobRecord
    from core.types.json import JSONDict

__all__ = ("build_read_video_progress_payload",)


def build_read_video_progress_payload(job: ReadVideoJobRecord) -> JSONDict:
    return {
        "stage": job.progress_stage,
        "percent_complete": job.percent_complete,
        "frames_done": job.frames_done,
        "frames_total_estimate": job.frames_total_estimate,
        "audio_chunks_done": job.audio_chunks_done,
        "audio_chunks_total_estimate": job.audio_chunks_total_estimate,
        "current_timestamp_seconds": job.current_timestamp_seconds,
    }
