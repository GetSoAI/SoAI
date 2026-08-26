"""SoAI - MCP read_video request probing, identity, and creation resolution [backend/mcp/tools/read_video_job_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.media.probing import probe_video
from mcp.tools.error import MCPToolError
from mcp.tools.read_video_identity import (
    compute_config_signature,
    compute_job_key,
    compute_source_signature,
)
from mcp.tools.read_video_job_builder import build_new_job_record
from mcp.tools.read_video_range import resolve_effective_range

if TYPE_CHECKING:
    from core.read_video.records import ReadVideoJobRecord
    from mcp.tools.read_video_engine_types import (
        ReadVideoEngineDeps,
        ReadVideoEngineRequest,
    )

__all__ = ("resolve_new_job",)


def _resolve_include_audio(request: ReadVideoEngineRequest, deps: ReadVideoEngineDeps) -> bool:
    if request.include_audio is None:
        return deps.config.include_audio_default
    return request.include_audio


async def resolve_new_job(
    request: ReadVideoEngineRequest,
    deps: ReadVideoEngineDeps,
) -> ReadVideoJobRecord:
    if request.resolved_path is None:
        raise MCPToolError(-32602, "file_path is required to start a new read_video job.")
    resolved_path = request.resolved_path
    try:
        probe = await probe_video(
            resolved_path,
            timeout_seconds=deps.config.probe_timeout_sec,
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, exception.message) from exception
    except SoAIError as exception:
        raise MCPToolError(-32603, exception.message) from exception
    resolved_range = resolve_effective_range(
        probe,
        start_seconds=request.start_seconds,
        end_seconds=request.end_seconds,
        requested_fps=request.requested_fps,
        config=deps.config,
    )
    include_audio = _resolve_include_audio(request, deps)
    source_signature = compute_source_signature(resolved_path)
    config_signature = compute_config_signature(deps.config)
    job_key = compute_job_key(
        config_signature=config_signature,
        resolved_path=resolved_path,
        source_signature=source_signature,
        range_start_seconds=resolved_range.range_start_seconds,
        range_end_seconds=resolved_range.range_end_seconds,
        frames_per_second=resolved_range.frames_per_second,
        include_audio=include_audio,
    )
    existing = await deps.repository.get_job_by_key(job_key)
    if existing is not None:
        return existing
    record = build_new_job_record(
        probe=probe,
        resolved_range=resolved_range,
        config=deps.config,
        resolved_path=resolved_path,
        owner_key=request.owner_key,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        active_task_id=request.active_task_id,
        active_tool_call_id=request.active_tool_call_id,
        include_audio=include_audio,
        source_size_bytes=source_signature.size_bytes,
        now_ms=deps.clock(),
        job_id=secrets.token_hex(16),
        job_key=job_key,
        config_signature=config_signature,
        source_signature=source_signature,
        page_size=deps.config.frame_page_size,
    )
    await deps.repository.create_job(record)
    created = await deps.repository.get_job_by_key(job_key)
    if created is None:
        raise StateError("read_video job vanished immediately after creation.")
    return created
