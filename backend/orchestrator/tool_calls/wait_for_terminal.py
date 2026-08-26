"""SoAI - Tool call terminal wait coordination [backend/orchestrator/tool_calls/wait_for_terminal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_remaining_clamped, is_deadline_expired
from core.timing.epoch import epoch_ms
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_ERROR,
    is_terminal_tool_call_status,
    resolve_terminal_tool_call_payload,
)
from core.validation.integers import is_non_negative_strict_int

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "is_tool_call_timeout_payload",
    "resolve_tool_call_timeout_duration_ms",
    "wait_for_existing_tool_call_terminal",
)

_TOOL_CALL_IN_PROGRESS_WAIT_TIMEOUT_SECONDS: float = 120.0
_TOOL_CALL_TIMEOUT_CODE: str = "tool_call_timeout"
_TOOL_CALL_MISSING_CODE: str = "tool_call_missing"


def _build_tool_call_timeout_payload() -> JSONDict:
    return {
        "error": "Tool call did not complete before its execution deadline.",
        "code": _TOOL_CALL_TIMEOUT_CODE,
    }


def _build_tool_call_missing_payload() -> JSONDict:
    return {
        "error": "Tool call is already in progress but the persisted record is missing.",
        "code": _TOOL_CALL_MISSING_CODE,
    }


def resolve_tool_call_timeout_duration_ms(existing_call: JSONDict | None) -> int:
    if existing_call is None:
        return 0
    started_at_ms = existing_call.get("started_at_ms")
    if not is_non_negative_strict_int(started_at_ms):
        return 0
    return max(0, int(epoch_ms()) - started_at_ms)


def is_tool_call_timeout_payload(value: JSONValue) -> bool:
    if not isinstance(value, dict):
        return False
    code_value = value.get("code")
    return code_value == _TOOL_CALL_TIMEOUT_CODE


async def wait_for_existing_tool_call_terminal(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    tool_context: MCPToolContext,
    storage_call_id: str,
    logger: LoggerProtocol,
    deadline_monotonic: float | None = None,
) -> JSONValue:
    start_time = time.monotonic()
    sleep_seconds = 0.05
    while True:
        now_monotonic = time.monotonic()
        elapsed = now_monotonic - start_time
        deadline_expired = deadline_monotonic is not None and is_deadline_expired(
            deadline_monotonic,
        )
        if elapsed >= _TOOL_CALL_IN_PROGRESS_WAIT_TIMEOUT_SECONDS or deadline_expired:
            logger.warning(
                "Tool call wait timed out (conv_id=%s, message_index=%s, storage_call_id=%s).",
                tool_context.conv_id,
                tool_context.message_index,
                storage_call_id,
            )
            timeout_payload = _build_tool_call_timeout_payload()
            finalized = await database_tool_calls.finalize_tool_call_if_unfinished(
                storage_call_id,
                status=TOOL_CALL_STATUS_ERROR,
                error_message=str(timeout_payload["error"]),
                completed_at_ms=epoch_ms(),
            )
            if finalized is not None:
                error_value = finalized.get("error")
                if error_value == timeout_payload["error"]:
                    return timeout_payload
                return resolve_terminal_tool_call_payload(finalized)
            return _build_tool_call_missing_payload()
        persisted = await database_tool_calls.get_tool_call_by_storage_id(storage_call_id)
        if persisted is None:
            return _build_tool_call_missing_payload()
        status_value = persisted.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if is_terminal_tool_call_status(status):
            return resolve_terminal_tool_call_payload(persisted)
        if deadline_monotonic is None:
            await asyncio.sleep(sleep_seconds)
        else:
            remaining = deadline_remaining_clamped(deadline_monotonic)
            await asyncio.sleep(min(sleep_seconds, remaining))
        sleep_seconds = min(1.0, sleep_seconds * 1.5)
