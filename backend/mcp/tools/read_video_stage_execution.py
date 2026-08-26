"""SoAI - MCP read_video parse stage execution with lease heartbeat [backend/mcp/tools/read_video_stage_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.read_video.enums import ReadVideoJobStatus
from mcp.tools.error import MCPToolError
from mcp.tools.read_video_engine_lease import finalize_with_lease
from mcp.tools.read_video_parse import run_parse_stages
from mcp.tools.read_video_progress_tracker import resolve_read_video_lease_ttl_ms

if TYPE_CHECKING:
    from core.media.job_storage import MediaJobPaths
    from core.read_video.records import ReadVideoJobRecord
    from mcp.tools.read_video_engine_types import ReadVideoEngineDeps
    from mcp.tools.read_video_preview import ReadVideoPreviewResult
    from mcp.tools.read_video_progress_tracker import ReadVideoProgressTracker

__all__ = ("execute_parse_stages_with_lease_heartbeat",)

_LOGGER_NAME = "SoAI.mcp.tools.read_video.stage_execution"
_OPERATION_READ_VIDEO_STAGE_EXECUTION = "mcp.tools.read_video.stage_execution"


async def _cancelled_parse_status(
    job: ReadVideoJobRecord,
    deps: ReadVideoEngineDeps,
) -> ReadVideoJobStatus:
    if job.active_task_id is None:
        return ReadVideoJobStatus.INTERRUPTED
    task = await deps.task_registry.get(job.active_task_id, force_refresh=True)
    if task is not None and task.cancellation_requested_at_ms is not None:
        return ReadVideoJobStatus.CANCELLED
    return ReadVideoJobStatus.INTERRUPTED


async def _execute_stages(
    job: ReadVideoJobRecord,
    *,
    deps: ReadVideoEngineDeps,
    tracker: ReadVideoProgressTracker,
    paths: MediaJobPaths,
    scratch_dir: str,
    preview_start: float,
    token: str,
) -> ReadVideoPreviewResult | None:
    try:
        return await run_parse_stages(
            job,
            deps=deps,
            tracker=tracker,
            paths=paths,
            scratch_dir=scratch_dir,
            preview_start_seconds=preview_start,
        )
    except asyncio.CancelledError:
        status = await _cancelled_parse_status(job, deps)
        await asyncio.shield(
            finalize_with_lease(deps.repository, job.job_id, token, status, deps.clock()),
        )
        raise
    except MCPToolError as exception:
        await asyncio.shield(
            finalize_with_lease(
                deps.repository,
                job.job_id,
                token,
                ReadVideoJobStatus.FAILED,
                deps.clock(),
                error_code=str(exception.code),
                error_message=exception.message,
            ),
        )
        raise
    except Exception as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=_OPERATION_READ_VIDEO_STAGE_EXECUTION,
        )
        log_exception(
            get_logger(_LOGGER_NAME),
            coerced,
            message="read_video stage execution failed.",
            operation=_OPERATION_READ_VIDEO_STAGE_EXECUTION,
        )
        error_message = coerced.message.strip() or "read_video parsing failed."
        await asyncio.shield(
            finalize_with_lease(
                deps.repository,
                job.job_id,
                token,
                ReadVideoJobStatus.FAILED,
                deps.clock(),
                error_code=exception.__class__.__name__,
                error_message=error_message,
            ),
        )
        raise


async def execute_parse_stages_with_lease_heartbeat(
    job: ReadVideoJobRecord,
    *,
    deps: ReadVideoEngineDeps,
    tracker: ReadVideoProgressTracker,
    paths: MediaJobPaths,
    scratch_dir: str,
    preview_start: float,
    token: str,
) -> ReadVideoPreviewResult | None:
    heartbeat_task = asyncio.create_task(
        tracker.run_lease_heartbeat(),
        name=f"read-video-lease-heartbeat-{job.job_id}",
    )
    stages_task = asyncio.create_task(
        _execute_stages(
            job,
            deps=deps,
            tracker=tracker,
            paths=paths,
            scratch_dir=scratch_dir,
            preview_start=preview_start,
            token=token,
        ),
        name=f"read-video-parse-stages-{job.job_id}",
    )
    try:
        wait_timeout_seconds = resolve_read_video_lease_ttl_ms(deps.config) / 1000.0
        while True:
            done, _pending = await asyncio.wait(
                (heartbeat_task, stages_task),
                return_when=asyncio.FIRST_COMPLETED,
                timeout=wait_timeout_seconds,
            )
            if not done:
                continue
            if heartbeat_task in done:
                await heartbeat_task
            return await stages_task
    finally:
        await cancel_and_await(
            (heartbeat_task, stages_task),
            task_label="read_video parse tasks",
        )
