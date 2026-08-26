"""SoAI - Deferred tool-call acceptance persistence [backend/orchestrator/tool_calls/deferred_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.tool_calls.deferred_tool_call_signal import take_deferred_marker
from orchestrator.tool_calls.execution_persistence import (
    persist_deferred_tool_call_accepted_result,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from orchestrator.tool_calls.persistence import ToolCallPersistenceContext

__all__ = ("DeferredToolCallAcceptance", "persist_deferred_tool_call_acceptance")


@dataclass(frozen=True, slots=True)
class DeferredToolCallAcceptance:
    result: JSONValue


async def persist_deferred_tool_call_acceptance(
    *,
    persistence_context: ToolCallPersistenceContext,
    storage_call_identifier: str,
    raw_result: JSONValue,
) -> DeferredToolCallAcceptance | None:
    marker = take_deferred_marker(raw_result)
    if not marker.deferred:
        return None
    if marker.accepted_state_persisted:
        return DeferredToolCallAcceptance(result=marker.result)
    await persist_deferred_tool_call_accepted_result(
        persistence_context,
        storage_call_identifier=storage_call_identifier,
        result_json=serialize_json_compact_stable(marker.result),
        owner_task_id=marker.owner_task_id,
    )
    return DeferredToolCallAcceptance(result=marker.result)
