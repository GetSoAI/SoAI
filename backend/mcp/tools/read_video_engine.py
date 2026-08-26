"""SoAI - MCP read_video job and lease orchestration engine entrypoint [backend/mcp/tools/read_video_engine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import SoAITimeoutError
from core.read_video.enums import ReadVideoJobStatus, ReadVideoLeaseResult
from core.tasks.task_cancellation import request_task_cancellation
from mcp.tools.error import MCPToolError
from mcp.tools.read_video_engine_lease import busy_error, finalize_with_lease
from mcp.tools.read_video_engine_types import (
    ReadVideoEngineDeps,
    ReadVideoEngineRequest,
)
from mcp.tools.read_video_job_resolution import resolve_new_job
from mcp.tools.read_video_lease_requests import acquire_read_video_lease
from mcp.tools.read_video_parse_runner import (
    fetch_terminal_result,
    run_parse,
    validate_cursor_identity,
)
from mcp.tools.read_video_progress_tracker import resolve_read_video_lease_ttl_ms
from mcp.tools.read_video_retention import cleanup_expired_jobs

if TYPE_CHECKING:
    from core.read_video.records import ReadVideoJobRecord
    from core.types.json import JSONDict

__all__ = ("ReadVideoEngineDeps", "ReadVideoEngineRequest", "run_read_video")

_SWEEP_LIMIT = 8


def _target_job_id(request: ReadVideoEngineRequest) -> str | None:
    if request.job_id is not None:
        return request.job_id
    if request.cursor is not None:
        return request.cursor.job_id
    return None


def _has_live_lease(job: ReadVideoJobRecord, now_ms: int) -> bool:
    return (
        job.lease_token is not None
        and job.lease_expires_at_ms is not None
        and job.lease_expires_at_ms >= now_ms
    )


async def run_read_video(request: ReadVideoEngineRequest, *, deps: ReadVideoEngineDeps) -> JSONDict:
    await cleanup_expired_jobs(deps, limit=_SWEEP_LIMIT)
    if request.cancel:
        return await _cancel(request, deps)
    target_id = _target_job_id(request)
    if target_id is not None:
        return await _resume_or_fetch(target_id, request, deps)
    job = await resolve_new_job(request, deps)
    if job.status == ReadVideoJobStatus.COMPLETED:
        return await fetch_terminal_result(job, request, deps)
    return await run_parse(job, request, deps)


async def _resume_or_fetch(
    target_id: str,
    request: ReadVideoEngineRequest,
    deps: ReadVideoEngineDeps,
) -> JSONDict:
    job = await deps.repository.get_job_by_id(target_id)
    if job is None:
        raise MCPToolError(-32602, "read_video job was not found.")
    validate_cursor_identity(request, job)
    if job.status == ReadVideoJobStatus.COMPLETED:
        return await fetch_terminal_result(job, request, deps)
    return await run_parse(job, request, deps)


async def _cancel(request: ReadVideoEngineRequest, deps: ReadVideoEngineDeps) -> JSONDict:
    target_id = _target_job_id(request)
    if target_id is None:
        raise MCPToolError(-32602, "read_video cancel requires job_id or cursor.")
    job = await deps.repository.get_job_by_id(target_id)
    if job is None:
        raise MCPToolError(-32602, "read_video job was not found.")
    validate_cursor_identity(request, job)
    if job.status.is_terminal():
        return await fetch_terminal_result(job, request, deps)
    now = deps.clock()
    if _has_live_lease(job, now):
        if job.active_task_id is None:
            raise busy_error(job)
        requested = await request_task_cancellation(
            deps.task_registry,
            job.active_task_id,
            reason="read_video cancellation requested.",
        )
        if requested is None:
            raise busy_error(job)
        try:
            await deps.task_registry.wait_for_completion(
                job.active_task_id,
                timeout=resolve_read_video_lease_ttl_ms(deps.config) / 1000.0,
            )
        except SoAITimeoutError as exception:
            refreshed = await deps.repository.get_job_by_id(job.job_id)
            raise busy_error(refreshed or job) from exception
        refreshed = await deps.repository.get_job_by_id(job.job_id)
        if refreshed is None:
            raise MCPToolError(-32602, "read_video job was not found.")
        if not refreshed.status.is_terminal():
            raise busy_error(refreshed)
        return await fetch_terminal_result(refreshed, request, deps)
    token, outcome_result, outcome_job = await acquire_read_video_lease(
        deps.repository,
        job,
        request,
        deps=deps,
        now_ms=now,
    )
    if outcome_result == ReadVideoLeaseResult.COMPLETED and outcome_job is not None:
        return await fetch_terminal_result(outcome_job, request, deps)
    if outcome_result != ReadVideoLeaseResult.ACQUIRED:
        raise busy_error(job)
    finalized = await finalize_with_lease(
        deps.repository,
        job.job_id,
        token,
        ReadVideoJobStatus.CANCELLED,
        deps.clock(),
    )
    cancelled = await deps.repository.get_job_by_id(job.job_id)
    if cancelled is None:
        raise MCPToolError(-32602, "read_video job was not found.")
    if not finalized or cancelled.status != ReadVideoJobStatus.CANCELLED:
        raise MCPToolError(-32603, "read_video could not finalize the cancelled job.")
    return await fetch_terminal_result(cancelled, request, deps)
