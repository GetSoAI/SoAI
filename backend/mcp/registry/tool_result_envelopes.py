"""SoAI - MCP tool execution result envelopes [backend/mcp/registry/tool_result_envelopes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable_strict
from core.tasks.enums import TaskStatus

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_background_task_envelope",
    "build_inline_tool_result",
    "build_proxied_task_completion_payload",
    "build_proxied_task_error_payload",
    "build_tool_task_completion_result",
    "extract_queued_task_id",
)


def build_inline_tool_result(result_payload: JSONValue) -> JSONDict:
    return {
        "content": [
            {
                "type": "text",
                "text": serialize_json_compact_stable_strict(result_payload),
            },
        ],
        "structuredContent": result_payload,
        "isError": False,
    }


def build_tool_task_completion_result(result_payload: JSONValue) -> JSONDict:
    return {
        "content": [{"type": "text", "text": serialize_json_compact_stable_strict(result_payload)}],
        "isError": False,
    }


def extract_queued_task_id(result: JSONValue) -> str | None:
    if not isinstance(result, dict):
        return None
    status_value = str(result.get("status") or "").strip().lower()
    if status_value != "queued":
        return None
    task_id_value = result.get("task_id")
    if not isinstance(task_id_value, str):
        return None
    task_id = task_id_value.strip()
    if not task_id:
        return None
    return task_id


def build_background_task_envelope(
    *,
    task_id: str,
    status: TaskStatus,
    result: JSONValue | None,
    error_message: str | None,
) -> JSONDict:
    background_task: JSONDict = {
        "task_id": task_id,
        "status": status.value,
    }
    if result is not None:
        background_task["result"] = result
    if error_message:
        background_task["error_message"] = error_message
    return background_task


def build_proxied_task_completion_payload(
    *,
    task_id: str,
    status: TaskStatus,
    result: JSONValue | None,
    error_message: str | None,
) -> JSONDict:
    completed_payload: JSONDict = {
        "background_task": build_background_task_envelope(
            task_id=task_id,
            status=status,
            result=result,
            error_message=error_message,
        ),
        "status": status.value,
    }
    if result is not None:
        completed_payload["result"] = result
    return completed_payload


def build_proxied_task_error_payload(
    *,
    task_id: str,
    status: TaskStatus,
    result: JSONValue | None,
    error_message: str,
) -> JSONDict:
    return {
        "error": error_message,
        "background_task": build_background_task_envelope(
            task_id=task_id,
            status=status,
            result=result,
            error_message=error_message,
        ),
    }
