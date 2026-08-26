"""SoAI - MCP read_video parse stage orchestration (frames, audio, preview) [backend/mcp/tools/read_video_parse.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.read_video_audio import ReadVideoAudioJob, extract_audio
from mcp.tools.read_video_frames import ReadVideoFrameJob, extract_frames
from mcp.tools.read_video_preview import ReadVideoPreviewJob, build_preview_clip

if TYPE_CHECKING:
    from core.media.job_storage import MediaJobPaths
    from core.read_video.records import ReadVideoJobRecord
    from mcp.tools.read_video_engine_types import ReadVideoEngineDeps
    from mcp.tools.read_video_preview import ReadVideoPreviewResult
    from mcp.tools.read_video_progress_tracker import ReadVideoProgressTracker

__all__ = ("run_parse_stages",)

_STAGE_FRAMES = "extracting_frames"
_STAGE_AUDIO = "transcribing_audio"
_STAGE_PREVIEW = "building_preview"


async def run_parse_stages(
    job: ReadVideoJobRecord,
    *,
    deps: ReadVideoEngineDeps,
    tracker: ReadVideoProgressTracker,
    paths: MediaJobPaths,
    scratch_dir: str,
    preview_start_seconds: float,
) -> ReadVideoPreviewResult | None:
    tracker.set_stage(_STAGE_FRAMES)
    await extract_frames(
        ReadVideoFrameJob(
            job_id=job.job_id,
            source_path=job.source_path,
            range_start_seconds=job.range_start_seconds,
            range_end_seconds=job.range_end_seconds,
            frames_per_second=job.frames_per_second,
            source_width=job.source_width,
            source_height=job.source_height,
            frames_dir=paths.frames_dir,
            scratch_dir=scratch_dir,
        ),
        config=deps.config,
        repository=deps.repository,
        storage_manager=deps.storage_manager,
        on_progress=tracker.on_frames,
    )
    if job.include_audio and job.audio_present:
        tracker.set_stage(_STAGE_AUDIO)
        await extract_audio(
            ReadVideoAudioJob(
                job_id=job.job_id,
                source_path=job.source_path,
                range_start_seconds=job.range_start_seconds,
                range_end_seconds=job.range_end_seconds,
                audio_dir=paths.audio_dir,
                scratch_dir=scratch_dir,
            ),
            config=deps.config,
            repository=deps.repository,
            storage_manager=deps.storage_manager,
            transcriber=deps.transcriber,
            on_progress=tracker.on_audio,
        )
    tracker.set_stage(_STAGE_PREVIEW)
    await tracker.flush_now()
    return await build_preview_clip(
        ReadVideoPreviewJob(
            job_id=job.job_id,
            source_path=job.source_path,
            start_seconds=preview_start_seconds,
            range_end_seconds=job.range_end_seconds,
            source_width=job.source_width,
            source_height=job.source_height,
            audio_present=job.audio_present,
            include_audio=job.include_audio,
            scratch_dir=scratch_dir,
        ),
        config=deps.config,
        storage_manager=deps.storage_manager,
    )
