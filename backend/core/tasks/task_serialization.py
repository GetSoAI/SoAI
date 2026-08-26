"""SoAI - Task validation and serialization helpers [backend/core/tasks/task_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import ValidationError
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.protocols_serialization import TaskSerializationSurfaceProtocol
from core.tasks.task_public_fields import resolve_public_task_terminal_fields
from core.types.dict import freeze_json_dict
from core.types.json import JSONValue
from core.types.json_value import copy_json_value
from core.types.pydantic_json_value import coerce_to_pydantic_json_dict
from core.validation.integers import is_non_negative_strict_int

__all__ = (
    "build_task_dict",
    "validate_and_normalize_task",
)


def validate_and_normalize_task(task: TaskSerializationSurfaceProtocol) -> None:
    if not isinstance(task.task_id, str):
        raise ValidationError("task_id must be a non-empty string.")
    normalized_task_id = task.task_id.strip()
    if not normalized_task_id:
        raise ValidationError("task_id must be a non-empty string.")
    if normalized_task_id != task.task_id:
        raise ValidationError("task_id must not include leading or trailing whitespace.")
    if not is_non_negative_strict_int(task.user_id):
        raise ValidationError("user_id must be a non-negative integer.")
    normalized_cancellation_id = require_cancellation_id(task.cancellation_id)
    if normalized_cancellation_id != task.cancellation_id:
        raise ValidationError("cancellation_id must not include leading or trailing whitespace.")
    if not isinstance(task.metadata, Mapping):
        raise ValidationError("metadata must be a mapping.")
    if task.result is not None and not isinstance(task.result, Mapping):
        raise ValidationError("result must be a mapping or None.")
    task.metadata = freeze_json_dict(task.metadata)
    if task.result is not None:
        coerced_result = coerce_to_pydantic_json_dict(task.result)
        task.result = (
            {key: copy_json_value(value) for key, value in coerced_result.items()}
            if coerced_result is not None
            else None
        )


def build_task_dict(
    task: TaskSerializationSurfaceProtocol,
    *,
    include_result: bool,
    include_metadata: bool,
) -> dict[str, JSONValue]:
    public_terminal_fields = resolve_public_task_terminal_fields(
        status=task.status,
        error_code=task.error_code,
        error_type=task.error_type,
        status_message=task.status_message,
        error_message=task.error_message,
    )
    data: dict[str, JSONValue] = {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status.value,
        "user_id": task.user_id,
        "owner_id": task.owner_id,
        "owner_type": task.owner_type,
        "cancellation_id": task.cancellation_id,
        "created_at_ms": task.created_at_ms,
        "updated_at_ms": task.updated_at_ms,
        "completed_at_ms": task.completed_at_ms,
        "ttl_ms": task.ttl_ms,
        "ttl_expires_at_ms": task.ttl_expires_at_ms,
        "poll_interval_ms": task.poll_interval_ms,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
        "progress_percent": task.progress_percent(),
        "status_message": public_terminal_fields.status_message,
        "cancellation_requested_at_ms": task.cancellation_requested_at_ms,
    }
    if include_metadata:
        data["metadata"] = (
            {key: copy_json_value(value) for key, value in task.metadata.items()}
            if task.metadata
            else {}
        )
    if include_result:
        data["result"] = (
            {key: copy_json_value(value) for key, value in task.result.items()}
            if task.result is not None
            else None
        )
        data["error_code"] = task.error_code
        data["error_type"] = task.error_type
        data["error_message"] = public_terminal_fields.error_message
    context = task.orchestration_context
    tracking_id = context.tracking_id if context else task.snapshot_tracking_id
    if tracking_id:
        data["tracking_id"] = tracking_id
    excluded_universal_ids = (
        context.excluded_universal_ids if context else task.snapshot_excluded_universal_ids
    )
    if excluded_universal_ids:
        data["excluded_uids"] = list(excluded_universal_ids)
    virtual_model_name = context.virtual_model_name if context else task.snapshot_virtual_model_name
    if virtual_model_name:
        data["virtual_model_name"] = virtual_model_name
    return data
