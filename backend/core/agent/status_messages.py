"""SoAI - Shared agent execution status message resolution [backend/core/agent/status_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_ERROR,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
    AGENT_TURN_STATUS_RUNNING,
)

__all__ = ("resolve_agent_execution_status_message",)


def resolve_agent_execution_status_message(
    status: str,
    error_message: str | None,
) -> str | None:
    normalized_error_message = (
        error_message.strip() if error_message is not None and error_message.strip() else None
    )
    if status == AGENT_TURN_STATUS_RUNNING:
        return "Running"
    if status == AGENT_TURN_STATUS_COMPLETED:
        return "Completed"
    if status == AGENT_TURN_STATUS_MAX_ITERATIONS:
        return "Max iterations reached"
    if status == AGENT_TURN_STATUS_CANCELLED:
        return normalized_error_message or "Cancelled"
    if status == AGENT_TURN_STATUS_ERROR:
        return normalized_error_message or "Failed"
    if status == AGENT_TURN_STATUS_ABANDONED:
        return normalized_error_message or "Abandoned"
    return normalized_error_message
