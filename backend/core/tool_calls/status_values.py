"""SoAI - Tool-call status constants and resolution helpers [backend/core/tool_calls/status_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.error_payloads import build_tool_call_error_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "TOOL_CALL_ACTIVE_STATUSES",
    "TOOL_CALL_FAILURE_STATUSES",
    "TOOL_CALL_PERSISTED_STATUSES",
    "TOOL_CALL_STATUS_CANCELLED",
    "TOOL_CALL_STATUS_COMPLETED",
    "TOOL_CALL_STATUS_ERROR",
    "TOOL_CALL_STATUS_PENDING",
    "TOOL_CALL_STATUS_RUNNING",
    "TOOL_CALL_TERMINAL_STATUSES",
    "is_active_tool_call_status",
    "is_failure_tool_call_status",
    "is_terminal_tool_call_status",
    "normalize_tool_call_status",
    "resolve_terminal_tool_call_payload",
    "resolve_tool_call_status_from_result_payload",
    "resolve_tool_call_status_rank",
)

TOOL_CALL_STATUS_PENDING = "pending"
TOOL_CALL_STATUS_RUNNING = "running"
TOOL_CALL_STATUS_COMPLETED = "completed"
TOOL_CALL_STATUS_CANCELLED = "cancelled"
TOOL_CALL_STATUS_ERROR = "error"

TOOL_CALL_ACTIVE_STATUSES: frozenset[str] = frozenset(
    (TOOL_CALL_STATUS_PENDING, TOOL_CALL_STATUS_RUNNING),
)
TOOL_CALL_TERMINAL_STATUSES: frozenset[str] = frozenset(
    (TOOL_CALL_STATUS_COMPLETED, TOOL_CALL_STATUS_CANCELLED, TOOL_CALL_STATUS_ERROR),
)
TOOL_CALL_FAILURE_STATUSES: frozenset[str] = frozenset(
    (TOOL_CALL_STATUS_CANCELLED, TOOL_CALL_STATUS_ERROR),
)
TOOL_CALL_PERSISTED_STATUSES: frozenset[str] = frozenset(
    (
        TOOL_CALL_STATUS_PENDING,
        TOOL_CALL_STATUS_RUNNING,
        TOOL_CALL_STATUS_COMPLETED,
        TOOL_CALL_STATUS_CANCELLED,
        TOOL_CALL_STATUS_ERROR,
    ),
)


def normalize_tool_call_status(status: str) -> str:
    return str(status or "").strip().lower()


def is_active_tool_call_status(status: str) -> bool:
    return normalize_tool_call_status(status) in TOOL_CALL_ACTIVE_STATUSES


def is_terminal_tool_call_status(status: str) -> bool:
    return normalize_tool_call_status(status) in TOOL_CALL_TERMINAL_STATUSES


def is_failure_tool_call_status(status: str) -> bool:
    normalized_status = normalize_tool_call_status(status)
    return normalized_status in TOOL_CALL_FAILURE_STATUSES


def resolve_tool_call_status_rank(status: str) -> int:
    normalized_status = normalize_tool_call_status(status)
    if normalized_status == TOOL_CALL_STATUS_PENDING:
        return 0
    if normalized_status == TOOL_CALL_STATUS_RUNNING:
        return 1
    if normalized_status == TOOL_CALL_STATUS_COMPLETED:
        return 2
    if normalized_status == TOOL_CALL_STATUS_CANCELLED:
        return 3
    return 4


def resolve_tool_call_status_from_result_payload(result_payload: JSONValue) -> str:
    if not isinstance(result_payload, dict):
        return TOOL_CALL_STATUS_COMPLETED
    code_value = result_payload.get("code")
    code = code_value.strip().lower() if isinstance(code_value, str) else ""
    if code == TOOL_CALL_STATUS_CANCELLED:
        return TOOL_CALL_STATUS_CANCELLED
    error_value = result_payload.get("error")
    if isinstance(error_value, str):
        return TOOL_CALL_STATUS_ERROR if error_value.strip() else TOOL_CALL_STATUS_COMPLETED
    if error_value is not None:
        return TOOL_CALL_STATUS_ERROR
    return TOOL_CALL_STATUS_COMPLETED


def resolve_terminal_tool_call_payload(existing_call: JSONDict) -> JSONValue:
    status_value = existing_call.get("status")
    status = normalize_tool_call_status(status_value if isinstance(status_value, str) else "")
    if status == TOOL_CALL_STATUS_COMPLETED:
        return existing_call.get("result")
    if status == TOOL_CALL_STATUS_CANCELLED:
        result_payload = existing_call.get("result")
        if result_payload is not None:
            return result_payload
        error_value = existing_call.get("error")
        error_message = error_value.strip() if isinstance(error_value, str) else ""
        return build_tool_call_error_payload(
            error_message=error_message or "Tool call cancelled.",
            code=TOOL_CALL_STATUS_CANCELLED,
        )
    if status == TOOL_CALL_STATUS_ERROR:
        result_payload = existing_call.get("result")
        if result_payload is not None:
            return result_payload
        error_value = existing_call.get("error")
        error_message = error_value.strip() if isinstance(error_value, str) else ""
        return build_tool_call_error_payload(
            error_message=error_message or "Tool call failed.",
            code="tool_call_error",
        )
    return build_tool_call_error_payload(
        error_message="Tool call is not in a terminal state.",
        code="in_progress",
    )
