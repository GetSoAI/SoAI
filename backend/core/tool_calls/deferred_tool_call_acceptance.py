"""SoAI - Deferred tool call accepted-state persistence [backend/core/tool_calls/deferred_tool_call_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.tool_calls.error_payloads import build_tool_call_error_payload
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_ERROR,
    is_active_tool_call_status,
    normalize_tool_call_status,
)

if TYPE_CHECKING:
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONValue

__all__ = (
    "persist_deferred_tool_call_accepted_state",
    "persist_deferred_tool_call_start_failure",
)


async def persist_deferred_tool_call_accepted_state(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    storage_call_id: str,
    owner_task_id: str,
    accepted_result: JSONValue,
) -> None:
    updated = await database_tool_calls.update_tool_call_result(
        storage_call_id,
        status=None,
        tool_result=serialize_json_compact_stable_strict(accepted_result),
        error_message=None,
        duration_ms=None,
        started_at_ms=None,
        completed_at_ms=None,
        owner_task_id=owner_task_id,
    )
    if updated is None:
        raise StateError("Deferred tool call accepted state requires a persisted tool call row.")
    updated_status_value = updated.get("status")
    updated_status = normalize_tool_call_status(
        updated_status_value if isinstance(updated_status_value, str) else "",
    )
    if not is_active_tool_call_status(updated_status):
        raise StateError("Deferred tool call accepted state lost to a terminal state.")
    updated_owner_task_id = updated.get("owner_task_id")
    if updated_owner_task_id != owner_task_id:
        raise StateError("Deferred tool call owner task binding did not persist.")


async def persist_deferred_tool_call_start_failure(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    storage_call_id: str,
    error_message: str,
) -> None:
    result_payload = build_tool_call_error_payload(
        error_message=error_message,
        code="server_error",
    )
    updated = await database_tool_calls.update_tool_call_result(
        storage_call_id,
        status=TOOL_CALL_STATUS_ERROR,
        tool_result=serialize_json_compact_stable_strict(result_payload),
        error_message=error_message,
        duration_ms=0,
        completed_at_ms=epoch_ms(),
    )
    if updated is None:
        raise StateError("Deferred tool call start failure requires a persisted tool call row.")
