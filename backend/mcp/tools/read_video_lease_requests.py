"""SoAI - Shared read_video lease request helpers [backend/mcp/tools/read_video_lease_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from core.read_video.enums import ReadVideoLeaseResult
from core.read_video.operations import ReadVideoLeaseRequest
from mcp.tools.error import MCPToolError
from mcp.tools.read_video_engine_lease import busy_error
from mcp.tools.read_video_progress_tracker import resolve_read_video_lease_ttl_ms

if TYPE_CHECKING:
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from core.read_video.records import ReadVideoJobRecord
    from mcp.tools.read_video_engine_types import (
        ReadVideoEngineDeps,
        ReadVideoEngineRequest,
    )

__all__ = (
    "acquire_read_video_lease",
    "build_read_video_lease_request",
)


def build_read_video_lease_request(
    job: ReadVideoJobRecord,
    request: ReadVideoEngineRequest,
    *,
    deps: ReadVideoEngineDeps,
    now_ms: int,
) -> tuple[str, ReadVideoLeaseRequest]:
    token = secrets.token_hex(16)
    return (
        token,
        ReadVideoLeaseRequest(
            job_id=job.job_id,
            lease_token=token,
            lease_owner=request.lease_owner,
            lease_expires_at_ms=now_ms + resolve_read_video_lease_ttl_ms(deps.config),
            now_ms=now_ms,
            active_task_id=request.active_task_id,
            active_tool_call_id=request.active_tool_call_id,
        ),
    )


async def acquire_read_video_lease(
    repository: DatabaseReadVideoJobsProtocol,
    job: ReadVideoJobRecord,
    request: ReadVideoEngineRequest,
    *,
    deps: ReadVideoEngineDeps,
    now_ms: int,
) -> tuple[str, ReadVideoLeaseResult, ReadVideoJobRecord | None]:
    token, lease_request = build_read_video_lease_request(
        job,
        request,
        deps=deps,
        now_ms=now_ms,
    )
    outcome = await repository.acquire_lease(lease_request)
    if outcome.result == ReadVideoLeaseResult.BUSY and outcome.job is not None:
        raise busy_error(outcome.job)
    if outcome.result == ReadVideoLeaseResult.NOT_FOUND:
        raise MCPToolError(-32602, "read_video job was not found.")
    return token, outcome.result, outcome.job
