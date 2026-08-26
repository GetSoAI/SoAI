"""SoAI - MCP task payload builders and parameter extraction [backend/mcp/server/handlers/task_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.timing.formatting import timestamp_ms_to_utc_iso

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_task_entry",
    "build_task_response",
    "extract_task_id_parameter",
)


def build_task_response(task: Task) -> JSONDict:
    response: JSONDict = {
        "taskId": task.task_id,
        "status": task.status.value,
        "createdAt": timestamp_ms_to_utc_iso(task.created_at_ms),
        "lastUpdatedAt": timestamp_ms_to_utc_iso(task.updated_at_ms),
    }
    if task.status_message and task.status not in (TaskStatus.FAILED, TaskStatus.COMPLETED):
        response["statusMessage"] = task.status_message
    if task.ttl_ms:
        response["ttl"] = int(task.ttl_ms)
    if task.poll_interval_ms:
        response["pollInterval"] = task.poll_interval_ms
    if task.progress_current is not None and task.progress_total is not None:
        response["progress"] = {
            "current": task.progress_current,
            "total": task.progress_total,
        }
    if task.status == TaskStatus.COMPLETED and task.result:
        response["result"] = task.result
    elif task.status == TaskStatus.FAILED:
        response["error"] = {
            "code": task.error_code if task.error_code is not None else -32603,
            "message": task.error_message or "Task failed",
        }
    return response


def build_task_entry(task: Task) -> JSONDict:
    metadata = task.metadata
    return {
        "taskId": task.task_id,
        "method": (method_value if isinstance(method_value := metadata.get("method"), str) else ""),
        "status": task.status.value,
    }


def extract_task_id_parameter(parameters: JSONDict) -> str | None:
    task_id_value = parameters.get("taskId")
    if isinstance(task_id_value, str):
        return task_id_value
    id_value = parameters.get("id")
    if isinstance(id_value, str):
        return id_value
    return None
