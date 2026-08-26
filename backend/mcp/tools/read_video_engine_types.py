"""SoAI - MCP read_video engine request and dependency contracts [backend/mcp/tools/read_video_engine_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.mcp.protocols_main import ReadAudioGatewayProtocol
    from core.read_video.operations import ReadVideoProgressUpdate
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from mcp.tools.read_video_config import ReadVideoConfig
    from mcp.tools.read_video_cursor import ReadVideoCursor

__all__ = ("ReadVideoEngineDeps", "ReadVideoEngineRequest")


@dataclass(frozen=True, slots=True)
class ReadVideoEngineRequest:
    resolved_path: str | None
    file_path: str
    owner_key: str
    user_id: str | None
    conversation_id: str | None
    active_task_id: str | None
    active_tool_call_id: str | None
    lease_owner: str
    requested_fps: float | None
    include_audio: bool | None
    start_seconds: float
    end_seconds: float | None
    job_id: str | None
    cursor: ReadVideoCursor | None
    cancel: bool


@dataclass(frozen=True, slots=True)
class ReadVideoEngineDeps:
    config: ReadVideoConfig
    app_config: ConfigProtocol
    repository: DatabaseReadVideoJobsProtocol
    task_registry: TaskRegistryProtocol
    storage_manager: StorageManagerProtocol
    transcriber: ReadAudioGatewayProtocol
    on_progress: Callable[[ReadVideoProgressUpdate], Awaitable[None]]
    clock: Callable[[], int]
