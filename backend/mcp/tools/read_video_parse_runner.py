"""SoAI - MCP read_video lease acquisition, parse execution, terminal reads [backend/mcp/tools/read_video_parse_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.media.job_storage import build_media_job_paths, build_media_scratch_directory
from core.read_video.enums import ReadVideoJobStatus, ReadVideoLeaseResult
from mcp.tools.error import MCPToolError
from mcp.tools.read_video_engine_lease import finalize_with_lease, release_and_cleanup
from mcp.tools.read_video_identity import compute_source_signature
from mcp.tools.read_video_lease_requests import acquire_read_video_lease
from mcp.tools.read_video_page import read_audio_page, read_frame_page
from mcp.tools.read_video_progress_tracker import ReadVideoProgressTracker
from mcp.tools.read_video_response import build_read_video_result
from mcp.tools.read_video_stage_execution import (
    execute_parse_stages_with_lease_heartbeat,
)

if TYPE_CHECKING:
    from core.read_video.records import ReadVideoJobRecord
    from core.types.json import JSONDict
    from mcp.tools.read_video_engine_types import (
        ReadVideoEngineDeps,
        ReadVideoEngineRequest,
    )
    from mcp.tools.read_video_preview import ReadVideoPreviewResult

__all__ = ("fetch_terminal_result", "request_offsets", "run_parse", "validate_cursor_identity")


class _CompletedDuringAcquire(Exception):
    __slots__ = ()


def validate_cursor_identity(request: ReadVideoEngineRequest, job: ReadVideoJobRecord) -> None:
    if request.cursor is None:
        return
    if request.job_id is not None and request.cursor.job_id != request.job_id:
        raise MCPToolError(-32602, "read_video cursor and job_id refer to different jobs.")
    if request.cursor.job_id != job.job_id:
        raise MCPToolError(-32602, "read_video cursor does not match the resolved job.")


def request_offsets(request: ReadVideoEngineRequest) -> tuple[int, int]:
    if request.cursor is None:
        return 0, 0
    return request.cursor.frame_offset, request.cursor.segment_offset


async def _acquire_for_parse(
    job: ReadVideoJobRecord,
    request: ReadVideoEngineRequest,
    deps: ReadVideoEngineDeps,
) -> tuple[ReadVideoJobRecord, str]:
    if compute_source_signature(job.source_path) != job.source_signature:
        raise MCPToolError(-32602, "read_video source changed; start a new job.")
    if (
        job.status != ReadVideoJobStatus.RUNNING
        and await deps.repository.count_running_jobs(request.owner_key, deps.clock())
        >= deps.config.max_active_jobs
    ):
        raise MCPToolError(
            -32603,
            "Too many active read_video jobs.",
            data={"owner_key": request.owner_key, "limit": deps.config.max_active_jobs},
        )
    now = deps.clock()
    token, outcome_result, outcome_job = await acquire_read_video_lease(
        deps.repository,
        job,
        request,
        deps=deps,
        now_ms=now,
    )
    if outcome_result == ReadVideoLeaseResult.COMPLETED or outcome_job is None:
        raise _CompletedDuringAcquire
    return outcome_job, token


def _preview_start(job: ReadVideoJobRecord, offset_frames: int) -> float:
    candidate = job.range_start_seconds + offset_frames / job.frames_per_second
    return max(job.range_start_seconds, min(job.range_end_seconds, candidate))


async def run_parse(
    job: ReadVideoJobRecord,
    request: ReadVideoEngineRequest,
    deps: ReadVideoEngineDeps,
) -> JSONDict:
    try:
        acquired, token = await _acquire_for_parse(job, request, deps)
    except _CompletedDuringAcquire:
        refreshed = await deps.repository.get_job_by_id(job.job_id)
        return await fetch_terminal_result(refreshed or job, request, deps)
    offset_frames, offset_segments = request_offsets(request)
    paths = build_media_job_paths(deps.app_config, "read-video", acquired.job_id)
    scratch_dir = build_media_scratch_directory(paths, token)
    tracker = ReadVideoProgressTracker(
        repository=deps.repository,
        job_id=acquired.job_id,
        lease_token=token,
        config=deps.config,
        on_progress=deps.on_progress,
        clock=deps.clock,
        range_start_seconds=acquired.range_start_seconds,
        frames_per_second=acquired.frames_per_second,
    )
    try:
        preview = await execute_parse_stages_with_lease_heartbeat(
            acquired,
            deps=deps,
            tracker=tracker,
            paths=paths,
            scratch_dir=scratch_dir,
            preview_start=_preview_start(acquired, offset_frames),
            token=token,
        )
        finalized = await asyncio.shield(
            finalize_with_lease(
                deps.repository,
                acquired.job_id,
                token,
                ReadVideoJobStatus.COMPLETED,
                deps.clock(),
            ),
        )
        final = await deps.repository.get_job_by_id(acquired.job_id) or acquired
        if not finalized or final.status != ReadVideoJobStatus.COMPLETED:
            raise MCPToolError(-32603, "read_video could not finalize the completed job.")
        return await _build_completed_result(final, deps, offset_frames, offset_segments, preview)
    finally:
        await asyncio.shield(
            release_and_cleanup(deps.repository, acquired.job_id, token, scratch_dir, deps.clock()),
        )


async def _build_completed_result(
    final: ReadVideoJobRecord,
    deps: ReadVideoEngineDeps,
    offset_frames: int,
    offset_segments: int,
    preview: ReadVideoPreviewResult | None,
) -> JSONDict:
    frame_page = await read_frame_page(
        deps.repository,
        final,
        start_index=offset_frames,
        limit=final.page_size,
    )
    audio_page = await read_audio_page(
        deps.repository,
        final,
        start_index=offset_segments,
        limit=final.page_size,
    )
    return build_read_video_result(
        job=final,
        status=ReadVideoJobStatus.COMPLETED,
        frame_page=frame_page,
        audio_page=audio_page,
        preview=preview,
        audio_requested=bool(final.include_audio),
        audio_skipped=(not final.include_audio) or (not final.audio_present),
    )


async def fetch_terminal_result(
    job: ReadVideoJobRecord,
    request: ReadVideoEngineRequest,
    deps: ReadVideoEngineDeps,
) -> JSONDict:
    validate_cursor_identity(request, job)
    offset_frames, offset_segments = request_offsets(request)
    frame_page = await read_frame_page(
        deps.repository,
        job,
        start_index=offset_frames,
        limit=job.page_size,
    )
    audio_page = await read_audio_page(
        deps.repository,
        job,
        start_index=offset_segments,
        limit=job.page_size,
    )
    return build_read_video_result(
        job=job,
        status=job.status,
        frame_page=frame_page,
        audio_page=audio_page,
        preview=None,
        audio_requested=bool(job.include_audio),
        audio_skipped=(not job.include_audio) or (not job.audio_present),
    )
