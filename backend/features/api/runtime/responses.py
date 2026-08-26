"""SoAI - API runtime response helpers [backend/features/api/runtime/responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Response, status
from fastapi.responses import JSONResponse

from core.errors.exceptions import StateError, ValidationError
from features.api.runtime.response_body import (
    create_json_body_response,
    parse_response_body_json_dict,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "apply_operation_id_header",
    "apply_task_id_header",
    "build_task_operation_headers",
    "create_dry_run_response",
    "create_json_response_with_task_id",
    "create_no_content_response",
    "create_task_accepted_response",
    "extract_task_id_from_accepted_response",
    "require_json_response",
)


def apply_operation_id_header(response: Response, operation_id: str | None) -> Response:
    if operation_id is None:
        return response
    response.headers["X-SoAI-Operation-Id"] = str(operation_id)
    return response


def apply_task_id_header(response: Response, task_id: str | None) -> Response:
    if task_id is None:
        return response
    response.headers["X-SoAI-Task-Id"] = str(task_id)
    return response


def build_task_operation_headers(
    *,
    task_id: str | None,
    operation_id: str | None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if task_id is not None:
        headers["X-SoAI-Task-Id"] = str(task_id)
    if operation_id is not None:
        headers["X-SoAI-Operation-Id"] = str(operation_id)
    return headers


def create_no_content_response() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def create_json_response_with_task_id(
    content: JSONValue,
    task_id: str,
    status_code: int = 200,
    operation_id: str | None = None,
) -> JSONResponse:
    response = create_json_body_response(status_code=status_code, content=content)
    apply_task_id_header(response, task_id)
    apply_operation_id_header(response, operation_id)
    return response


def create_task_accepted_response(
    *,
    task_id: str,
    commit_deadline_ts_ms: int | None,
    extra: JSONDict | None = None,
    operation_id: str | None = None,
    preference_applied: str | None = None,
) -> JSONResponse:
    payload: JSONDict = dict(extra or {})
    payload["status"] = "accepted"
    payload["task_id"] = task_id
    if commit_deadline_ts_ms is not None:
        payload["commit_deadline_ts_ms"] = int(commit_deadline_ts_ms)
    response = create_json_response_with_task_id(
        payload,
        task_id,
        status.HTTP_202_ACCEPTED,
        operation_id=operation_id,
    )
    if preference_applied is not None:
        response.headers["Preference-Applied"] = preference_applied
    return response


def require_json_response(response: Response, *, operation: str, message: str) -> JSONResponse:
    if not isinstance(response, JSONResponse):
        raise StateError(message, operation=operation)
    return response


def create_dry_run_response(
    planned_commands: list[list[str]],
    predicted_effects: list[str],
    warnings: list[str],
    *,
    extra: JSONDict | None = None,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    payload: JSONDict = {
        "dry_run": True,
        "planned_commands": planned_commands,
        "predicted_effects": predicted_effects,
        "warnings": warnings,
    }
    if extra:
        payload.update(extra)
    return create_json_body_response(status_code=status_code, content=payload)


def extract_task_id_from_accepted_response(response: JSONResponse, *, operation: str) -> str:
    header_task_id = response.headers.get("X-SoAI-Task-Id")
    if isinstance(header_task_id, str) and header_task_id.strip():
        return header_task_id.strip()
    try:
        payload = parse_response_body_json_dict(response, field="accepted response body")
    except ValidationError as exception:
        raise StateError("Accepted response body is not JSON.", operation=operation) from exception
    raw = payload.get("task_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise StateError("Accepted response missing task_id.", operation=operation)
