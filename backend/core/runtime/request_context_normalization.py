"""SoAI - Request context normalization helpers [backend/core/runtime/request_context_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.turn_scope_values import TURN_SCOPE_ALL
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

__all__ = (
    "normalize_optional_non_negative_int",
    "normalize_optional_string",
    "normalize_optional_turn_scope",
    "normalize_required_cancellation_id",
    "resolve_context_identifier_args",
)


def resolve_context_identifier_args(
    args: tuple[str | None, ...],
    *,
    task_id: str | None,
    trace_id: str | None,
    client_ip: str | None,
) -> tuple[str | None, str | None, str | None]:
    if not args:
        return task_id, trace_id, client_ip
    if len(args) > 3:
        raise ValidationError(
            "RequestContext accepts at most 3 positional arguments (task_id, trace_id, client_ip).",
        )
    if trace_id is not None or client_ip is not None or task_id is not None:
        raise ValidationError(
            "RequestContext received both positional and keyword context identifiers.",
        )
    resolved_task_id = args[0] if args else None
    resolved_trace_id = args[1] if len(args) >= 2 else None
    resolved_client_ip = args[2] if len(args) >= 3 else None
    return resolved_task_id, resolved_trace_id, resolved_client_ip


def normalize_optional_string(value: str | None, *, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string when provided.")
    normalized = value.strip()
    return normalized or None


def normalize_optional_non_negative_int(value: int | None, *, label: str) -> int | None:
    if value is None:
        return None
    if not is_strict_int(value):
        raise ValidationError(f"{label} must be an integer when provided.")
    if value < 0:
        raise ValidationError(f"{label} must be non-negative when provided.")
    return int(value)


def normalize_required_cancellation_id(value: str | None) -> str:
    normalized = normalize_optional_string(
        value,
        label="RequestContext.cancellation_id",
    )
    if normalized is None:
        raise ValidationError("RequestContext requires cancellation_id.")
    return normalized


def normalize_optional_turn_scope(value: str | None) -> str | None:
    normalized = normalize_optional_string(
        value,
        label="RequestContext.agent_turn_scope",
    )
    if normalized is None:
        return None
    if normalized not in TURN_SCOPE_ALL:
        raise ValidationError(
            "RequestContext.agent_turn_scope must be root or subagent when provided.",
        )
    return normalized
