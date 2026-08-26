"""SoAI - Subagent parent tool call update error reporting [backend/features/agent/subagents/parent_tool_call_update_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_FINALIZE",
    "OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_LIVE",
    "log_parent_tool_call_update_failure",
)

OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_FINALIZE = (
    "agent.subagents.parent_tool_call_updates.finalize"
)
OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_LIVE = "agent.subagents.parent_tool_call_updates.live"


def log_parent_tool_call_update_failure(
    *,
    logger: LoggerProtocol,
    exception: Exception,
    trace_id: str,
    operation: str,
    message: str,
    call_id: str,
) -> None:
    log_exception(
        logger,
        exception,
        message=message,
        trace_id=trace_id,
        operation=operation,
        level="warning",
        details={"call_id": call_id},
    )
