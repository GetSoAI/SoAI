"""SoAI - Automation turn limits and normalization [backend/core/automation/automation_turn_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_constants import (
    AUTOMATION_DEFAULT_MAX_RUN_MINUTES,
    AUTOMATION_DEFAULT_MAX_TURN_CHARS,
    AUTOMATION_DEFAULT_MAX_TURNS,
    AUTOMATION_HARD_MAX_RUN_MINUTES,
    AUTOMATION_HARD_MAX_TURN_CHARS,
    AUTOMATION_HARD_MAX_TURNS,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_positive_strict_int, is_strict_int

__all__ = (
    "normalize_automation_max_run_minutes",
    "normalize_automation_max_turn_chars",
    "normalize_automation_max_turns",
    "normalize_automation_turns",
    "require_automation_limits_snapshot",
    "require_automation_max_run_minutes_snapshot",
)


def normalize_automation_max_turns(value: JSONValue, *, field_label: str) -> int:
    return _normalize_limit(
        value,
        field_label=field_label,
        default=AUTOMATION_DEFAULT_MAX_TURNS,
        maximum=AUTOMATION_HARD_MAX_TURNS,
    )


def normalize_automation_max_turn_chars(value: JSONValue, *, field_label: str) -> int:
    return _normalize_limit(
        value,
        field_label=field_label,
        default=AUTOMATION_DEFAULT_MAX_TURN_CHARS,
        maximum=AUTOMATION_HARD_MAX_TURN_CHARS,
    )


def require_automation_limits_snapshot(limits_snapshot: JSONDict) -> tuple[int, int]:
    max_turns_value = limits_snapshot.get("max_turns")
    max_turn_chars_value = limits_snapshot.get("max_turn_chars")
    max_turns = _require_positive_int(
        max_turns_value,
        field_label="Automation limits_snapshot.max_turns",
    )
    max_turn_chars = _require_positive_int(
        max_turn_chars_value,
        field_label="Automation limits_snapshot.max_turn_chars",
    )
    return (max_turns, max_turn_chars)


def normalize_automation_max_run_minutes(value: JSONValue, *, field_label: str) -> int:
    return _normalize_limit(
        value,
        field_label=field_label,
        default=AUTOMATION_DEFAULT_MAX_RUN_MINUTES,
        maximum=AUTOMATION_HARD_MAX_RUN_MINUTES,
    )


def require_automation_max_run_minutes_snapshot(limits_snapshot: JSONDict) -> int:
    return _require_positive_int(
        limits_snapshot.get("max_run_minutes"),
        field_label="Automation limits_snapshot.max_run_minutes",
    )


def normalize_automation_turns(
    value: JSONValue,
    *,
    max_turns: int,
    max_turn_chars: int,
    label: str,
) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{label} must be a non-empty array.")
    if len(value) > max_turns:
        message = "".join(
            (
                f"{label} cannot exceed {max_turns}. ",
                "Each turn is executed as one agent turn; combine sub-instructions into fewer turns.",
            ),
        )
        raise ValidationError(
            message,
        )
    normalized: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str):
            raise ValidationError(f"{label} turn {index + 1} must be a string.")
        turn_text = entry.strip()
        if not turn_text:
            raise ValidationError(f"{label} turn {index + 1} cannot be empty.")
        if len(turn_text) > max_turn_chars:
            raise ValidationError(
                f"{label} turn {index + 1} cannot exceed {max_turn_chars} characters.",
            )
        normalized.append(turn_text)
    return normalized


def _require_positive_int(value: JSONValue, *, field_label: str) -> int:
    if not is_positive_strict_int(value):
        raise ValidationError(f"{field_label} must be a positive integer.")
    return int(value)


def _normalize_limit(
    value: JSONValue,
    *,
    field_label: str,
    default: int,
    maximum: int,
) -> int:
    if value is None:
        return int(default)
    if not is_strict_int(value):
        raise ValidationError(f"{field_label} must be an integer.")
    if value <= 0:
        raise ValidationError(f"{field_label} must be greater than zero.")
    if value > maximum:
        raise ValidationError(f"{field_label} cannot exceed {maximum}.")
    return int(value)
