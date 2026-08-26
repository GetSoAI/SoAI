"""SoAI - Plugin API task finalization and response wiring [backend/features/api/routes/plugins/plugin_task_api_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import Request
from fastapi.responses import JSONResponse

from core.tasks.enums import TaskStatus
from core.validation.integers import is_strict_int
from features.api.runtime.responses import create_json_response_with_task_id
from features.api.runtime.task_api_errors import raise_api_error_with_task
from features.api.runtime.task_execution import finalize_task_safely

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginActionResponseProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.routes.plugins.plugin_task_preparation import PreparedPluginTask

__all__ = (
    "build_plugin_task_api_response",
    "raise_prepared_plugin_task_error",
)


def _build_task_response_payload(
    payload: JSONDict | None,
    *,
    task_id: str,
) -> JSONDict:
    response_payload = dict(payload or {})
    response_payload["task_id"] = task_id
    return response_payload


def _resolve_status_code(value: int | None) -> int:
    if value is None:
        return 500
    if not is_strict_int(value):
        return 500
    return int(value)


def _read_status_code(response: PluginActionResponseProtocol) -> int | None:
    try:
        status_code = response.status_code
    except AttributeError:
        return None
    if is_strict_int(status_code):
        return int(status_code)
    return None


def _read_error_type(response: PluginActionResponseProtocol) -> str | None:
    try:
        error_type = response.error_type
    except AttributeError:
        return None
    if isinstance(error_type, str):
        trimmed = error_type.strip()
        return trimmed or None
    return None


def _is_cancelled_response(response: PluginActionResponseProtocol) -> bool:
    if _read_status_code(response) == 499:
        return True
    error_type = _read_error_type(response)
    return isinstance(error_type, str) and error_type.strip().lower() == "cancelled"


async def build_plugin_task_api_response(
    request: Request,
    *,
    prepared_task: PreparedPluginTask,
    response: PluginActionResponseProtocol,
    operation: str,
    success_status_message: str,
    default_failure_message: str,
    details: dict[str, JSONValue],
) -> JSONResponse:
    status_code = _resolve_status_code(_read_status_code(response))
    task_id = prepared_task.task_id
    payload = response.payload if isinstance(response.payload, dict) else {}
    if response.success:
        message_value = payload.get("message")
        await finalize_task_safely(
            registry=prepared_task.registry,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            operation=f"{operation}.complete_task",
            trace_id=prepared_task.trace_id,
            result=payload,
            status_message=(message_value if isinstance(message_value, str) else None)
            or success_status_message,
            details=details,
        )
        return create_json_response_with_task_id(
            _build_task_response_payload(payload, task_id=task_id),
            task_id,
            status_code,
        )

    error_type = response.error_type or "plugin_action_failed"
    error_message = response.error_message or default_failure_message
    if _is_cancelled_response(response):
        cancel_reason = str(error_message or "").strip() or "Cancelled by user"
        await finalize_task_safely(
            registry=prepared_task.registry,
            task_id=task_id,
            status=TaskStatus.CANCELLED,
            operation=f"{operation}.finalize_cancelled",
            trace_id=prepared_task.trace_id,
            error_message=cancel_reason,
            status_message=cancel_reason,
            details=details,
        )
    else:
        await finalize_task_safely(
            registry=prepared_task.registry,
            task_id=task_id,
            status=TaskStatus.FAILED,
            operation=f"{operation}.fail_task",
            trace_id=prepared_task.trace_id,
            error_code=status_code or 500,
            error_message=error_message,
            details=details,
        )
    raise_api_error_with_task(
        request,
        status_code,
        error_type,
        error_message,
        task_id=task_id,
        extra=response.extra,
    )


async def raise_prepared_plugin_task_error(
    request: Request,
    *,
    prepared_task: PreparedPluginTask,
    status_code: int,
    error_type: str,
    error_message: str,
    operation: str,
    details: dict[str, JSONValue],
    extra: JSONDict | None = None,
) -> NoReturn:
    task_id = prepared_task.task_id
    await finalize_task_safely(
        registry=prepared_task.registry,
        task_id=task_id,
        status=TaskStatus.FAILED,
        operation=operation,
        trace_id=prepared_task.trace_id,
        error_code=status_code,
        error_message=error_message,
        details=details,
    )
    raise_api_error_with_task(
        request,
        status_code,
        error_type,
        error_message,
        task_id=task_id,
        extra=extra,
    )
