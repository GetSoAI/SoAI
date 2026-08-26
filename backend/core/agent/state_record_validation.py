"""SoAI - Shared agent state record normalization [backend/core/agent/state_record_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Never

from core.agent.plan_validation import (
    MAX_AGENT_PLAN_MARKDOWN_LENGTH,
    MAX_AGENT_PLAN_TITLE_LENGTH,
    normalize_plan_markdown,
    normalize_plan_title,
)
from core.agent.todo_state_validation import (
    MAX_AGENT_TODO_EXPLANATION_LENGTH,
    MAX_AGENT_TODO_ITEM_LENGTH,
    MAX_AGENT_TODO_ITEMS,
    normalize_agent_todo_state_payload,
)
from core.errors.exceptions import ValidationError
from core.validation.record_fields import require_int, require_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_default_agent_plan_record",
    "build_default_agent_todo_record",
    "normalize_agent_plan_record",
    "normalize_agent_todo_record",
)


def build_default_agent_plan_record(*, conv_id: str, user_id: int) -> JSONDict:
    return {
        "conv_id": conv_id,
        "user_id": int(user_id),
        "revision": 0,
        "updated_at_ms": None,
        "title": None,
        "markdown": None,
    }


def build_default_agent_todo_record(*, conv_id: str, user_id: int) -> JSONDict:
    return {
        "conv_id": conv_id,
        "user_id": int(user_id),
        "revision": 0,
        "updated_at_ms": None,
        "explanation": None,
        "todo": [],
    }


def _raise_record_error(
    build_error: Callable[[str], Exception],
    message: str,
    *,
    exception: Exception | None = None,
) -> Never:
    error = build_error(message)
    if exception is None:
        raise error
    raise error from exception


def _require_optional_non_negative_int(
    record: JSONDict,
    *,
    field_name: str,
    build_error: Callable[[str], Exception],
) -> int | None:
    value = record.get(field_name)
    if value is None:
        return None
    try:
        return require_int(
            value,
            label=f"Agent state field '{field_name}'",
            build_error=build_error,
            minimum=0,
        )
    except ValidationError as exception:
        _raise_record_error(
            build_error,
            f"Agent state field '{field_name}' is invalid.",
            exception=exception,
        )


def normalize_agent_plan_record(
    record: JSONDict | None,
    *,
    conv_id: str,
    user_id: int,
    build_error: Callable[[str], Exception],
) -> JSONDict:
    if record is None:
        return build_default_agent_plan_record(conv_id=conv_id, user_id=user_id)
    try:
        record_conv_id = require_non_empty_str(
            record.get("conv_id"),
            label="Agent state field 'conv_id'",
            build_error=build_error,
        )
        record_user_id = require_int(
            record.get("user_id"),
            label="Agent state field 'user_id'",
            build_error=build_error,
            minimum=1,
        )
        revision = require_int(
            record.get("revision"),
            label="Agent state field 'revision'",
            build_error=build_error,
            minimum=0,
        )
        updated_at_ms = _require_optional_non_negative_int(
            record,
            field_name="updated_at_ms",
            build_error=build_error,
        )
        title = normalize_plan_title(
            record.get("title"),
            max_length=MAX_AGENT_PLAN_TITLE_LENGTH,
        )
        markdown_value = record.get("markdown")
        markdown = (
            None
            if markdown_value is None
            else normalize_plan_markdown(
                markdown_value,
                max_length=MAX_AGENT_PLAN_MARKDOWN_LENGTH,
            )
        )
        if markdown is None:
            title = None
    except ValidationError as exception:
        _raise_record_error(build_error, "Agent plan record is invalid.", exception=exception)
    return {
        "conv_id": record_conv_id,
        "user_id": int(record_user_id),
        "revision": int(revision),
        "updated_at_ms": updated_at_ms,
        "title": title,
        "markdown": markdown,
    }


def normalize_agent_todo_record(
    record: JSONDict | None,
    *,
    conv_id: str,
    user_id: int,
    build_error: Callable[[str], Exception],
) -> JSONDict:
    if record is None:
        return build_default_agent_todo_record(conv_id=conv_id, user_id=user_id)
    try:
        record_conv_id = require_non_empty_str(
            record.get("conv_id"),
            label="Agent state field 'conv_id'",
            build_error=build_error,
        )
        record_user_id = require_int(
            record.get("user_id"),
            label="Agent state field 'user_id'",
            build_error=build_error,
            minimum=1,
        )
        revision = require_int(
            record.get("revision"),
            label="Agent state field 'revision'",
            build_error=build_error,
            minimum=0,
        )
        updated_at_ms = _require_optional_non_negative_int(
            record,
            field_name="updated_at_ms",
            build_error=build_error,
        )
        todo, explanation = normalize_agent_todo_state_payload(
            todo_value=record.get("todo", []),
            explanation_value=record.get("explanation"),
            max_items=MAX_AGENT_TODO_ITEMS,
            max_item_length=MAX_AGENT_TODO_ITEM_LENGTH,
            max_explanation_length=MAX_AGENT_TODO_EXPLANATION_LENGTH,
        )
    except ValidationError as exception:
        _raise_record_error(build_error, "Agent todo record is invalid.", exception=exception)
    return {
        "conv_id": record_conv_id,
        "user_id": int(record_user_id),
        "revision": int(revision),
        "updated_at_ms": updated_at_ms,
        "explanation": explanation,
        "todo": [dict(entry) for entry in todo],
    }
