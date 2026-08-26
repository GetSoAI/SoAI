"""SoAI - Agent todo state normalization and validation [backend/core/agent/todo_state_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue

__all__ = (
    "MAX_AGENT_TODO_EXPLANATION_LENGTH",
    "MAX_AGENT_TODO_ITEMS",
    "MAX_AGENT_TODO_ITEM_LENGTH",
    "VALID_TODO_ITEM_STATUSES",
    "normalize_agent_todo_explanation",
    "normalize_agent_todo_items",
    "normalize_agent_todo_state_payload",
)

VALID_TODO_ITEM_STATUSES: frozenset[str] = frozenset({"pending", "in_progress", "completed"})
MAX_AGENT_TODO_ITEMS: int = 64
MAX_AGENT_TODO_ITEM_LENGTH: int = 200
MAX_AGENT_TODO_EXPLANATION_LENGTH: int = 2000


def normalize_agent_todo_explanation(value: JSONValue, *, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("explanation must be a string when provided.")
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > int(max_length):
        raise ValidationError(f"explanation must be at most {int(max_length)} characters.")
    return stripped


def normalize_agent_todo_items(
    value: JSONValue,
    *,
    max_items: int,
    max_item_length: int,
) -> list[JSONDict]:
    if not isinstance(value, list):
        raise ValidationError("todo must be a list.")
    if len(value) > int(max_items):
        raise ValidationError(f"todo must contain at most {int(max_items)} items.")
    if not value:
        return []
    items: list[JSONDict] = []
    in_progress_count = 0
    for index, raw_item in enumerate(value):
        if not isinstance(raw_item, dict):
            raise ValidationError(f"todo[{index}] must be an object.")
        step_value = raw_item.get("step")
        status_value = raw_item.get("status")
        if not isinstance(step_value, str) or not step_value.strip():
            raise ValidationError(f"todo[{index}].step must be a non-empty string.")
        step = step_value.strip()
        if len(step) > int(max_item_length):
            raise ValidationError(
                f"todo[{index}].step must be at most {int(max_item_length)} characters.",
            )
        if not isinstance(status_value, str) or not status_value.strip():
            raise ValidationError(f"todo[{index}].status must be a non-empty string.")
        status = status_value.strip()
        if status not in VALID_TODO_ITEM_STATUSES:
            raise ValidationError(
                f"todo[{index}].status must be one of: pending, in_progress, completed.",
            )
        if status == "in_progress":
            in_progress_count += 1
        items.append({"step": step, "status": status})
    if in_progress_count > 1:
        raise ValidationError("todo must contain at most one in_progress item.")
    if in_progress_count == 0:
        all_completed = all(item["status"] == "completed" for item in items)
        if not all_completed:
            raise ValidationError(
                "todo must contain exactly one in_progress item when any item is pending.",
            )
    return items


def normalize_agent_todo_state_payload(
    *,
    todo_value: JSONValue,
    explanation_value: JSONValue,
    max_items: int,
    max_item_length: int,
    max_explanation_length: int,
) -> tuple[list[JSONDict], str | None]:
    explanation = normalize_agent_todo_explanation(
        explanation_value,
        max_length=max_explanation_length,
    )
    todo = normalize_agent_todo_items(
        todo_value,
        max_items=max_items,
        max_item_length=max_item_length,
    )
    return todo, explanation
