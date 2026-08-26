"""SoAI - Deferred tool call result marker signaling [backend/core/tool_calls/deferred_tool_call_signal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DEFERRED_TOOL_CALL_RESULT_KEY",
    "DeferredToolCallMarker",
    "mark_result_deferred",
    "take_deferred_marker",
)

DEFERRED_TOOL_CALL_RESULT_KEY = "soai_deferred_tool_call_marker"
DEFERRED_TOOL_CALL_OWNER_TASK_ID_KEY = "soai_deferred_tool_call_owner_task_id"
DEFERRED_TOOL_CALL_ACCEPTED_STATE_PERSISTED_KEY = "soai_deferred_tool_call_accepted_state_persisted"


@dataclass(frozen=True, slots=True)
class DeferredToolCallMarker:
    deferred: bool
    result: JSONValue
    owner_task_id: str | None
    accepted_state_persisted: bool


def mark_result_deferred(
    result: JSONDict,
    *,
    owner_task_id: str | None = None,
    accepted_state_persisted: bool = False,
) -> JSONDict:
    marked = dict(result)
    marked[DEFERRED_TOOL_CALL_RESULT_KEY] = True
    if accepted_state_persisted:
        marked[DEFERRED_TOOL_CALL_ACCEPTED_STATE_PERSISTED_KEY] = True
    if owner_task_id is not None:
        normalized_owner_task_id = owner_task_id.strip()
        if not normalized_owner_task_id:
            raise ValidationError("Deferred tool call owner_task_id must not be empty.")
        marked[DEFERRED_TOOL_CALL_OWNER_TASK_ID_KEY] = normalized_owner_task_id
    return marked


def take_deferred_marker(result: JSONValue) -> DeferredToolCallMarker:
    if not isinstance(result, dict) or DEFERRED_TOOL_CALL_RESULT_KEY not in result:
        return DeferredToolCallMarker(
            deferred=False,
            result=result,
            owner_task_id=None,
            accepted_state_persisted=False,
        )
    owner_task_id_value = result.get(DEFERRED_TOOL_CALL_OWNER_TASK_ID_KEY)
    owner_task_id = None
    if owner_task_id_value is not None:
        if not isinstance(owner_task_id_value, str) or not owner_task_id_value.strip():
            raise ValidationError("Deferred tool call owner_task_id must be a non-empty string.")
        owner_task_id = owner_task_id_value.strip()
    accepted_state_persisted = result.get(DEFERRED_TOOL_CALL_ACCEPTED_STATE_PERSISTED_KEY) is True
    marker_keys = (
        DEFERRED_TOOL_CALL_RESULT_KEY,
        DEFERRED_TOOL_CALL_OWNER_TASK_ID_KEY,
        DEFERRED_TOOL_CALL_ACCEPTED_STATE_PERSISTED_KEY,
    )
    clean_result = {key: value for key, value in result.items() if key not in marker_keys}
    return DeferredToolCallMarker(
        deferred=True,
        result=clean_result,
        owner_task_id=owner_task_id,
        accepted_state_persisted=accepted_state_persisted,
    )
