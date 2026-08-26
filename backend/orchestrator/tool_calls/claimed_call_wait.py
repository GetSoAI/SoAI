"""SoAI - Claimed tool-call wait result handling [backend/orchestrator/tool_calls/claimed_call_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrator.tool_calls.execution_persistence import (
    persist_tool_call_timeout_result,
)
from orchestrator.tool_calls.wait_for_terminal import (
    is_tool_call_timeout_payload,
    resolve_tool_call_timeout_duration_ms,
    wait_for_existing_tool_call_terminal,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONValue
    from orchestrator.tool_calls.persistence import (
        ToolCallExecutionRecord,
        ToolCallPersistenceContext,
    )

__all__ = ("wait_for_claimed_tool_call_result",)


async def wait_for_claimed_tool_call_result(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    persistence_context: ToolCallPersistenceContext,
    record: ToolCallExecutionRecord,
    tool_context: MCPToolContext,
    storage_call_identifier: str,
    logger: LoggerProtocol,
    deadline_monotonic: float | None,
) -> JSONValue:
    payload = await wait_for_existing_tool_call_terminal(
        database_tool_calls=database_tool_calls,
        tool_context=tool_context,
        storage_call_id=storage_call_identifier,
        logger=logger,
        deadline_monotonic=deadline_monotonic,
    )
    if is_tool_call_timeout_payload(payload) and isinstance(payload, dict):
        existing_call = await database_tool_calls.get_tool_call_by_storage_id(
            storage_call_identifier,
        )
        return await persist_tool_call_timeout_result(
            persistence_context,
            record=record,
            result_payload=payload,
            duration_ms=resolve_tool_call_timeout_duration_ms(existing_call),
        )
    return payload
