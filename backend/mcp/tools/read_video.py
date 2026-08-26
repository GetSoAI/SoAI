"""SoAI - MCP utility tool: read_video [backend/mcp/tools/read_video.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.type_catalog import TASK_TYPE_MCP_TOOL_CALL
from core.timing.epoch import epoch_ms
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.read_video_arguments import (
    ReadVideoArguments,
    parse_read_video_arguments,
)
from mcp.tools.read_video_config import resolve_read_video_config
from mcp.tools.read_video_engine import run_read_video
from mcp.tools.read_video_engine_types import (
    ReadVideoEngineDeps,
    ReadVideoEngineRequest,
)
from mcp.tools.read_video_task_updates import publish_read_video_progress

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("tool_read_video",)

_LOGGER_NAME = "SoAI.mcp.tools.read_video"
_OPERATION_READ_VIDEO_TOOL = "mcp.tools.read_video"


def _conversation_id(utility_tools: MCPUtilityToolsProtocol) -> str | None:
    identity = utility_tools.active_tool_call_context.get(None)
    if identity is not None:
        return identity.conv_id
    context = utility_tools.active_request_context.get(None)
    tool_context = context.mcp_tool_context if context is not None else None
    if tool_context is None:
        return None
    return tool_context.conv_id


async def _create_task(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    owner_key: str,
    parsed: ReadVideoArguments,
) -> Task:
    cancellation_id = build_soai_id(("task", "mcp", "read_video", uuid.uuid4().hex[:12]))
    metadata: JSONDict = {
        "tool_name": "read_video",
        "owner_key": owner_key,
        "file_path": parsed.file_path,
        "range_start_seconds": parsed.start_seconds,
        "frames_per_second": parsed.frames_per_second,
        "include_audio": parsed.include_audio,
    }
    if parsed.end_seconds is not None:
        metadata["range_end_seconds"] = parsed.end_seconds
    if parsed.job_id is not None:
        metadata["read_video_job_id"] = parsed.job_id
    if parsed.cursor is not None:
        metadata["read_video_job_id"] = parsed.cursor.job_id
    return await create(
        utility_tools.task_registry,
        task_type=TASK_TYPE_MCP_TOOL_CALL,
        user_id=user_id,
        owner_id=owner_key,
        owner_type="mcp_client",
        cancellation_id=cancellation_id,
        status=TaskStatus.WORKING,
        status_message="read_video started",
        progress_total=100,
        metadata=metadata,
    )


async def _bind_current_task(utility_tools: MCPUtilityToolsProtocol, task: Task) -> None:
    current_task = asyncio.current_task()
    if current_task is None:
        return
    await utility_tools.task_cancellation_binder.bind_task(
        task.cancellation_id,
        current_task,
        owner="mcp.tools.read_video",
        metadata={"task_id": task.task_id, "tool_name": "read_video"},
    )


def _build_request(
    parsed: ReadVideoArguments,
    *,
    owner_key: str,
    user_id: int,
    conversation_id: str | None,
    task_id: str,
    active_tool_call_id: str | None,
) -> ReadVideoEngineRequest:
    identity = parsed
    return ReadVideoEngineRequest(
        resolved_path=identity.resolved_path,
        file_path=identity.file_path,
        owner_key=owner_key,
        user_id=str(user_id),
        conversation_id=conversation_id,
        active_task_id=task_id,
        active_tool_call_id=active_tool_call_id,
        lease_owner=task_id,
        requested_fps=identity.frames_per_second,
        include_audio=identity.include_audio,
        start_seconds=identity.start_seconds,
        end_seconds=identity.end_seconds,
        job_id=identity.job_id,
        cursor=identity.cursor,
        cancel=identity.cancel,
    )


async def tool_read_video(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="read_video",
        message="User authentication required for read_video.",
    )
    parsed = parse_read_video_arguments(utility_tools, arguments)
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    active_identity = utility_tools.active_tool_call_context.get(None)
    task = await _create_task(utility_tools, user_id=user_id, owner_key=owner_key, parsed=parsed)
    await _bind_current_task(utility_tools, task)
    try:
        result = await run_read_video(
            _build_request(
                parsed,
                owner_key=owner_key,
                user_id=user_id,
                conversation_id=_conversation_id(utility_tools),
                task_id=task.task_id,
                active_tool_call_id=(
                    active_identity.storage_call_id if active_identity is not None else None
                ),
            ),
            deps=ReadVideoEngineDeps(
                config=resolve_read_video_config(utility_tools.config),
                app_config=utility_tools.config,
                repository=utility_tools.database_read_video,
                task_registry=utility_tools.task_registry,
                storage_manager=utility_tools.storage_manager,
                transcriber=utility_tools.read_audio_gateway,
                on_progress=lambda progress: publish_read_video_progress(
                    utility_tools,
                    progress,
                    task_id=task.task_id,
                ),
                clock=epoch_ms,
            ),
        )
    except asyncio.CancelledError:
        await asyncio.shield(
            finalize(
                utility_tools.task_registry,
                task.task_id,
                TaskStatus.CANCELLED,
                error_message="read_video was cancelled.",
                status_message="read_video cancelled",
            ),
        )
        raise
    except MCPToolError as exception:
        await finalize(
            utility_tools.task_registry,
            task.task_id,
            TaskStatus.FAILED,
            error_code=int(exception.code),
            error_message=exception.message,
            status_message="read_video failed",
        )
        raise
    except Exception as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=_OPERATION_READ_VIDEO_TOOL,
        )
        log_exception(
            get_logger(_LOGGER_NAME),
            coerced,
            message="read_video tool failed.",
            operation=_OPERATION_READ_VIDEO_TOOL,
        )
        await finalize(
            utility_tools.task_registry,
            task.task_id,
            TaskStatus.FAILED,
            error_message=coerced.message,
            status_message="read_video failed",
        )
        raise MCPToolError(-32603, coerced.message) from exception
    status = str(result.get("status") or "")
    if status == "cancelled":
        await finalize(
            utility_tools.task_registry,
            task.task_id,
            TaskStatus.CANCELLED,
            result=result,
            status_message="read_video cancelled",
        )
    elif status == "failed":
        await finalize(
            utility_tools.task_registry,
            task.task_id,
            TaskStatus.FAILED,
            result=result,
            error_message="read_video failed",
            status_message="read_video failed",
        )
    else:
        await finalize(
            utility_tools.task_registry,
            task.task_id,
            TaskStatus.COMPLETED,
            result=result,
            status_message="read_video completed",
        )
    return result
