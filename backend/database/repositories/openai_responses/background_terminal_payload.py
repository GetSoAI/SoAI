"""SoAI - Terminal background Response payload projection [backend/database/repositories/openai_responses/background_terminal_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.errors.http_status_classification import resolve_openai_error_type_for_http_status
from core.openai.response_terminal_policy import (
    coerce_response_status,
    is_successful_response_status,
)
from core.openai.responses_events import (
    build_canonical_response_json,
    build_failed_response_json,
    build_response_status_json,
)
from core.tasks.enums import TaskStatus
from core.tasks.task_public_fields import resolve_public_task_terminal_fields
from database.core.json_codec import safe_json_deserialize_required_object

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_background_response_terminal_payload",)


def build_background_response_terminal_payload(
    *,
    response_id: str,
    model: str,
    created_at: int,
    task_status: str,
    result: str | None,
    error_code: int | None,
    error_type: str | None = None,
    error_message: str | None,
    status_message: str | None,
) -> JSONDict:
    if task_status == TaskStatus.COMPLETED.value:
        decoded_result = safe_json_deserialize_required_object(
            result,
            error_message="Completed background Responses task result must be a JSON object.",
        )
        response_status = coerce_response_status(
            decoded_result.get("status"),
            default_status="completed",
        )
        if not is_successful_response_status(response_status):
            raise StateError("Completed background Responses task has an invalid result status.")
        decoded_result["id"] = response_id
        return build_canonical_response_json(
            response_json=decoded_result,
            response_id=response_id,
            status=response_status,
            model=model,
            created_at=created_at,
        )
    if task_status == TaskStatus.FAILED.value:
        public_fields = resolve_public_task_terminal_fields(
            status=TaskStatus.FAILED,
            error_code=error_code,
            error_type=error_type,
            status_message=status_message,
            error_message=error_message,
        )
        resolved_error_code = error_code if error_code is not None else 500
        message = public_fields.error_message or public_fields.status_message or "Task failed."
        return build_failed_response_json(
            response_id=response_id,
            message=message,
            code=error_type or resolve_openai_error_type_for_http_status(resolved_error_code),
            model=model,
            created_at=created_at,
        )
    if task_status == TaskStatus.CANCELLED.value:
        return build_response_status_json(
            response_id=response_id,
            status="cancelled",
            model=model,
            created_at=created_at,
        )
    raise StateError("Background Response projection requires a terminal task status.")
