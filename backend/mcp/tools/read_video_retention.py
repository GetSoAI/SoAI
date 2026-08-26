"""SoAI - MCP read_video expired-job artifact retention sweep [backend/mcp/tools/read_video_retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.media.job_storage import build_media_job_paths, remove_media_tree

if TYPE_CHECKING:
    from mcp.tools.read_video_engine_types import ReadVideoEngineDeps

__all__ = ("cleanup_expired_jobs",)

_LOGGER_NAME = "SoAI.mcp.tools.read_video.retention"
_OPERATION_READ_VIDEO_RETENTION = "mcp.tools.read_video.retention"


async def cleanup_expired_jobs(deps: ReadVideoEngineDeps, *, limit: int) -> None:
    try:
        now_ms = deps.clock()
        expired = await deps.repository.list_expired_jobs(now_ms, limit)
        for job in expired:
            paths = build_media_job_paths(deps.app_config, "read-video", job.job_id)
            remove_media_tree(paths.job_root)
            await deps.repository.delete_job(job.job_id)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=_OPERATION_READ_VIDEO_RETENTION,
        )
        log_exception(
            get_logger(_LOGGER_NAME),
            coerced,
            message="read_video retention sweep failed.",
            operation=_OPERATION_READ_VIDEO_RETENTION,
        )
