"""SoAI - MCP read_video lease finalization, release, and cleanup helpers [backend/mcp/tools/read_video_engine_lease.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.media.job_storage import remove_media_tree
from core.read_video.enums import ReadVideoJobStatus
from mcp.tools.error import MCPToolError
from mcp.tools.read_video_progress_payload import build_read_video_progress_payload

if TYPE_CHECKING:
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from core.read_video.records import ReadVideoJobRecord

__all__ = ("busy_error", "finalize_with_lease", "release_and_cleanup")


def busy_error(job: ReadVideoJobRecord) -> MCPToolError:
    return MCPToolError(
        -32603,
        "read_video job is already being processed.",
        data={
            "job_id": job.job_id,
            "task_id": job.active_task_id,
            "progress": build_read_video_progress_payload(job),
        },
    )


async def finalize_with_lease(
    repository: DatabaseReadVideoJobsProtocol,
    job_id: str,
    lease_token: str,
    status: ReadVideoJobStatus,
    now_ms: int,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
) -> bool:
    if status == ReadVideoJobStatus.FAILED:
        return await repository.finalize_job(
            job_id,
            lease_token,
            status,
            error_code,
            error_message,
            now_ms,
        )
    return await repository.finalize_job(job_id, lease_token, status, None, None, now_ms)


async def release_and_cleanup(
    repository: DatabaseReadVideoJobsProtocol,
    job_id: str,
    lease_token: str,
    scratch_dir: str,
    now_ms: int,
) -> None:
    await repository.release_lease(job_id, lease_token, now_ms)
    remove_media_tree(scratch_dir)
