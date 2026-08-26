"""SoAI - Shared agent todo-state parsing helpers [backend/core/agent/todo_state_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.todo_state_validation import (
    MAX_AGENT_TODO_EXPLANATION_LENGTH,
    MAX_AGENT_TODO_ITEM_LENGTH,
    MAX_AGENT_TODO_ITEMS,
    normalize_agent_todo_state_payload,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.strict_numbers import require_non_negative_int_strict

__all__ = (
    "parse_agent_todo_state_from_turn_record",
    "parse_agent_todo_state_payload",
    "render_agent_todo_state_payload",
)


def parse_agent_todo_state_payload(payload: JSONDict | None) -> AgentTurnTodoState:
    if payload is None:
        return _build_default_todo_state()
    if not isinstance(payload, dict):
        raise ValidationError("todo_state must be an object.")
    todo_entries, explanation = normalize_agent_todo_state_payload(
        todo_value=payload.get("todo"),
        explanation_value=payload.get("explanation"),
        max_items=MAX_AGENT_TODO_ITEMS,
        max_item_length=MAX_AGENT_TODO_ITEM_LENGTH,
        max_explanation_length=MAX_AGENT_TODO_EXPLANATION_LENGTH,
    )
    revision = require_non_negative_int_strict(
        payload.get("revision", 0),
        error_message="todo_state.revision must be a non-negative integer.",
    )
    updated_at_raw = payload.get("updated_at_ms")
    updated_at_ms = (
        None
        if updated_at_raw is None
        else require_non_negative_int_strict(
            updated_at_raw,
            error_message="todo_state.updated_at_ms must be a non-negative integer.",
        )
    )
    return AgentTurnTodoState(
        todo=todo_entries,
        todo_explanation=explanation,
        todo_revision=revision,
        todo_updated_at_ms=updated_at_ms,
    )


def parse_agent_todo_state_from_turn_record(turn_record: JSONDict) -> AgentTurnTodoState:
    if not isinstance(turn_record, dict):
        raise ValidationError("Agent turn todo state record is invalid.")
    todo_entries, explanation = normalize_agent_todo_state_payload(
        todo_value=turn_record.get("todo"),
        explanation_value=turn_record.get("todo_explanation"),
        max_items=MAX_AGENT_TODO_ITEMS,
        max_item_length=MAX_AGENT_TODO_ITEM_LENGTH,
        max_explanation_length=MAX_AGENT_TODO_EXPLANATION_LENGTH,
    )
    revision = require_non_negative_int_strict(
        turn_record.get("todo_revision", 0),
        error_message="todo_state.todo_revision must be a non-negative integer.",
    )
    return AgentTurnTodoState(
        todo=todo_entries,
        todo_explanation=explanation,
        todo_revision=revision,
        todo_updated_at_ms=None,
    )


def render_agent_todo_state_payload(state: AgentTurnTodoState) -> JSONDict:
    return {
        "revision": int(state.todo_revision),
        "updated_at_ms": (
            int(state.todo_updated_at_ms) if state.todo_updated_at_ms is not None else None
        ),
        "explanation": state.todo_explanation,
        "todo": [dict(entry) for entry in state.todo],
    }


def _build_default_todo_state() -> AgentTurnTodoState:
    return AgentTurnTodoState(
        todo=[],
        todo_explanation=None,
        todo_revision=0,
        todo_updated_at_ms=None,
    )
