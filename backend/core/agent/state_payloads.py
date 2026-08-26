"""SoAI - Shared agent state revision and payload helpers [backend/core/agent/state_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.state_record_validation import (
    normalize_agent_plan_record,
    normalize_agent_todo_record,
)
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import (
        DatabaseAgentEventSequencesProtocol,
        DatabaseAgentPlanProtocol,
        DatabaseAgentTodoStateProtocol,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NormalizedAgentPlanState",
    "NormalizedAgentTodoState",
    "build_persisted_agent_plan_payload",
    "build_persisted_agent_todo_payload",
    "next_agent_state_updated_at_ms",
    "read_agent_plan_payload",
    "read_agent_todo_payload",
    "reserve_agent_state_revision",
)


@dataclass(frozen=True, slots=True)
class NormalizedAgentPlanState:
    payload: JSONDict
    title: str | None
    markdown: str | None


@dataclass(frozen=True, slots=True)
class NormalizedAgentTodoState:
    payload: JSONDict
    explanation: str | None
    todo: list[JSONDict]


def _build_plan_record_from_read(
    *,
    record: JSONDict | None,
    conv_id: str,
    user_id: int,
) -> JSONDict | None:
    if record is None:
        return None
    return {
        "conv_id": conv_id,
        "user_id": int(user_id),
        "revision": record.get("revision"),
        "updated_at_ms": record.get("updated_at_ms"),
        "title": record.get("title"),
        "markdown": record.get("markdown"),
    }


def _build_todo_record_from_read(
    *,
    record: JSONDict | None,
    conv_id: str,
    user_id: int,
) -> JSONDict | None:
    if record is None:
        return None
    return {
        "conv_id": conv_id,
        "user_id": int(user_id),
        "revision": record.get("revision"),
        "updated_at_ms": record.get("updated_at_ms"),
        "explanation": record.get("explanation"),
        "todo": record.get("todo"),
    }


def require_reserved_agent_state_revision(payload: JSONDict) -> int:
    if not isinstance(payload, dict):
        raise StateError("Agent state allocator returned an invalid payload.")
    start_sequence = payload.get("start_sequence")
    end_sequence = payload.get("end_sequence")
    if not is_strict_int(start_sequence):
        raise StateError("Agent state allocator returned an invalid start_sequence.")
    if not is_strict_int(end_sequence):
        raise StateError("Agent state allocator returned an invalid end_sequence.")
    if start_sequence <= 0 or end_sequence != start_sequence:
        raise StateError("Agent state allocator returned an invalid sequence reservation.")
    return int(start_sequence)


async def reserve_agent_state_revision(
    *,
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol,
    conv_id: str,
    user_id: int,
) -> int:
    payload = await database_agent_event_sequences.reserve_sequence_range(
        conv_id=conv_id,
        user_id=user_id,
        count=1,
    )
    return require_reserved_agent_state_revision(payload)


async def read_agent_plan_payload(
    *,
    database_agent_plan: DatabaseAgentPlanProtocol,
    conv_id: str,
    user_id: int,
) -> JSONDict:
    record = _build_plan_record_from_read(
        record=await database_agent_plan.read_plan(conv_id=conv_id, user_id=user_id),
        conv_id=conv_id,
        user_id=user_id,
    )
    return normalize_agent_plan_record(
        record,
        conv_id=conv_id,
        user_id=user_id,
        build_error=StateError,
    )


def build_persisted_agent_plan_payload(
    *,
    conv_id: str,
    user_id: int,
    revision: int,
    updated_at_ms: int,
    title_value: JSONValue,
    markdown_value: JSONValue,
) -> NormalizedAgentPlanState:
    payload = normalize_agent_plan_record(
        {
            "conv_id": conv_id,
            "user_id": int(user_id),
            "revision": int(revision),
            "updated_at_ms": int(updated_at_ms),
            "title": title_value,
            "markdown": markdown_value,
        },
        conv_id=conv_id,
        user_id=user_id,
        build_error=StateError,
    )
    markdown = payload.get("markdown")
    if markdown is not None and not isinstance(markdown, str):
        raise StateError("Agent plan payload is invalid.")
    title = payload.get("title")
    if markdown is None:
        title = None
    return NormalizedAgentPlanState(
        payload=payload,
        title=title if isinstance(title, str) else None,
        markdown=markdown if isinstance(markdown, str) else None,
    )


async def read_agent_todo_payload(
    *,
    database_agent_todo_state: DatabaseAgentTodoStateProtocol,
    conv_id: str,
    user_id: int,
) -> JSONDict:
    record = _build_todo_record_from_read(
        record=await database_agent_todo_state.get_todo_state(conv_id=conv_id, user_id=user_id),
        conv_id=conv_id,
        user_id=user_id,
    )
    return normalize_agent_todo_record(
        record,
        conv_id=conv_id,
        user_id=user_id,
        build_error=StateError,
    )


def build_persisted_agent_todo_payload(
    *,
    conv_id: str,
    user_id: int,
    revision: int,
    updated_at_ms: int,
    todo_value: JSONValue,
    explanation_value: JSONValue,
) -> NormalizedAgentTodoState:
    payload = normalize_agent_todo_record(
        {
            "conv_id": conv_id,
            "user_id": int(user_id),
            "revision": int(revision),
            "updated_at_ms": int(updated_at_ms),
            "explanation": explanation_value,
            "todo": todo_value,
        },
        conv_id=conv_id,
        user_id=user_id,
        build_error=StateError,
    )
    todo = payload.get("todo")
    if not isinstance(todo, list):
        raise StateError("Agent todo payload is invalid.")
    explanation = payload.get("explanation")
    todo_entries: list[JSONDict] = []
    for entry in todo:
        if not isinstance(entry, dict):
            raise StateError("Agent todo payload is invalid.")
        normalized_entry: JSONDict = {}
        for key, value in entry.items():
            if not isinstance(key, str):
                raise StateError("Agent todo payload is invalid.")
            normalized_entry[key] = value
        todo_entries.append(normalized_entry)
    return NormalizedAgentTodoState(
        payload=payload,
        explanation=explanation if isinstance(explanation, str) else None,
        todo=todo_entries,
    )


def next_agent_state_updated_at_ms() -> int:
    return epoch_ms()
