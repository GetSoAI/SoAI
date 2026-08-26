"""SoAI - Task conversion utilities for database rows [backend/tasks/registry/conversion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.enums import TaskStatus
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeCatalog, is_orchestrated_inference_task_type
from core.types.dict import freeze_json_dict
from core.types.json_value import copy_json_value
from core.types.pydantic_json_value import coerce_to_pydantic_json_dict
from core.validation.numberish import (
    require_int_from_numberish,
    require_optional_int_from_numberish,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "resolve_cancellation_id",
    "task_from_row",
)

OPERATION = "task_registry.task_from_row"


def resolve_cancellation_id(row: JSONDict) -> str:
    raw_value = row.get("cancellation_id")
    if raw_value is None:
        return require_cancellation_id(None)
    if isinstance(raw_value, bool):
        return require_cancellation_id(int(raw_value))
    if isinstance(raw_value, int):
        return require_cancellation_id(raw_value)
    if isinstance(raw_value, str):
        return require_cancellation_id(raw_value)
    return require_cancellation_id(str(raw_value))


def task_from_row(task_catalog: TaskTypeCatalog, row: JSONDict) -> Task:
    metadata_raw = row.get("metadata")
    metadata: dict[str, JSONValue]
    if metadata_raw is None:
        metadata = {}
    elif isinstance(metadata_raw, dict):
        metadata = {
            key: copy_json_value(value)
            for key, value in coerce_to_pydantic_json_dict(metadata_raw).items()
        }
    else:
        raise ValidationError(
            "Persisted task metadata must be a JSON object or null.",
            operation=OPERATION,
            details={"task_id": row.get("task_id")},
        )
    result_value = row.get("result")
    result: dict[str, JSONValue] | None
    if result_value is None:
        result = None
    elif isinstance(result_value, dict):
        result = {
            key: copy_json_value(value)
            for key, value in coerce_to_pydantic_json_dict(result_value).items()
        }
    else:
        raise ValidationError(
            "Persisted task result must be a JSON object or null.",
            operation=OPERATION,
            details={"task_id": row.get("task_id")},
        )
    task = Task(
        task_id=str(row["task_id"]),
        task_type=task_catalog.require(str(row["task_type"])),
        status=TaskStatus(str(row["status"])),
        user_id=require_int_from_numberish(row.get("user_id"), field="user_id"),
        owner_id=str(row["owner_id"]),
        owner_type=str(row["owner_type"]),
        cancellation_id=resolve_cancellation_id(row),
        created_at_ms=require_int_from_numberish(row.get("created_at_ms"), field="created_at_ms"),
        updated_at_ms=require_int_from_numberish(row.get("updated_at_ms"), field="updated_at_ms"),
        completed_at_ms=require_optional_int_from_numberish(
            row.get("completed_at_ms"),
            field="completed_at_ms",
        ),
        ttl_ms=require_optional_int_from_numberish(row.get("ttl_ms"), field="ttl_ms"),
        poll_interval_ms=require_int_from_numberish(
            row.get("poll_interval_ms"),
            field="poll_interval_ms",
        ),
        progress_current=(
            require_int_from_numberish(row.get("progress_current"), field="progress_current")
            if row.get("progress_current") is not None
            else None
        ),
        progress_total=(
            require_int_from_numberish(row.get("progress_total"), field="progress_total")
            if row.get("progress_total") is not None
            else None
        ),
        status_message=(
            str(row["status_message"]) if row.get("status_message") is not None else None
        ),
        progress_details=(
            str(row["progress_details"]) if row.get("progress_details") is not None else None
        ),
        metadata=freeze_json_dict(metadata),
        result=(result if result is not None else None),
        error_code=(require_optional_int_from_numberish(row.get("error_code"), field="error_code")),
        error_type=(str(row["error_type"]) if row.get("error_type") is not None else None),
        error_message=(str(row["error_message"]) if row.get("error_message") is not None else None),
        cancellation_requested_at_ms=(
            require_optional_int_from_numberish(
                row.get("cancellation_requested_at_ms"),
                field="cancellation_requested_at_ms",
            )
        ),
    )
    orchestration_state = row.get("orchestration_state")
    if is_orchestrated_inference_task_type(task.task_type):
        if not isinstance(orchestration_state, dict) or not orchestration_state:
            if task.status.is_terminal():
                return task
            raise StateError(
                "Persisted orchestrated task is missing orchestration_state.",
                operation=OPERATION,
                details={"task_id": task.task_id},
            )
        task = task.with_orchestration_context(
            OrchestrationContext.from_persisted_dict(orchestration_state),
            mark_updated=False,
        )
    return task
