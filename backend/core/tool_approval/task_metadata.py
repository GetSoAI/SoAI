"""SoAI - Tool approval task metadata helpers [backend/core/tool_approval/task_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_approval.constants import TOOL_APPROVAL_INTERACTION_TYPE
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_tool_approval_task_metadata",
    "extract_tool_approval_prompt_payload",
    "require_tool_approval_notification_id",
    "require_tool_approval_tool_key",
    "require_tool_approval_tool_name",
)


def build_tool_approval_task_metadata(
    *,
    conv_id: str,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    tool_name: str,
    tool_key: str | None,
    tool_arguments: str | None,
    notification_id: str,
) -> JSONDict:
    normalized_tool_name = coerce_optional_trimmed_str(tool_name)
    if normalized_tool_name is None:
        raise ValidationError("tool_name is required.")
    normalized_notification_id = coerce_optional_trimmed_str(notification_id)
    if normalized_notification_id is None:
        raise ValidationError("notification_id is required.")
    summary = f"Approve tool call: {normalized_tool_name}"
    return {
        "interaction_type": TOOL_APPROVAL_INTERACTION_TYPE,
        "conv_id": str(conv_id),
        "turn_id": str(turn_id),
        "iteration_index": int(iteration_index),
        "tool_call_id": str(tool_call_id),
        "tool_name": normalized_tool_name,
        "tool_key": tool_key,
        "tool_arguments": tool_arguments,
        "summary": summary,
        "notification_id": normalized_notification_id,
    }


def require_tool_approval_notification_id(metadata: Mapping[str, JSONValue]) -> str:
    notification_id = coerce_optional_trimmed_str(metadata.get("notification_id"))
    if notification_id is None:
        raise ValidationError("Tool approval task notification_id is missing.")
    return notification_id


def require_tool_approval_tool_name(metadata: Mapping[str, JSONValue]) -> str:
    tool_name = coerce_optional_trimmed_str(metadata.get("tool_name"))
    if tool_name is None:
        raise ValidationError("Tool approval task tool_name is missing.")
    return tool_name


def require_tool_approval_tool_key(metadata: Mapping[str, JSONValue]) -> str:
    tool_key = coerce_optional_trimmed_str(metadata.get("tool_key"))
    if tool_key is not None:
        return tool_key
    tool_name = coerce_optional_trimmed_str(metadata.get("tool_name"))
    if tool_name is not None:
        return tool_name
    raise ValidationError("Task does not specify a tool name.")


def extract_tool_approval_prompt_payload(task: Task) -> JSONDict | None:
    metadata = task.metadata
    interaction_type = metadata.get("interaction_type")
    if (
        not isinstance(interaction_type, str)
        or interaction_type.strip() != TOOL_APPROVAL_INTERACTION_TYPE
    ):
        return None
    tool_name = coerce_optional_trimmed_str(metadata.get("tool_name"))
    if tool_name is None:
        return None
    tool_call_id = coerce_optional_trimmed_str(metadata.get("tool_call_id"))
    tool_arguments = metadata.get("tool_arguments")
    return {
        "task_id": task.task_id,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "tool_arguments": tool_arguments,
        "created_at_ms": int(task.created_at_ms),
    }
