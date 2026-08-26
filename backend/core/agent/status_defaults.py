"""SoAI - Canonical agent-turn status defaults [backend/core/agent/status_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_ERROR,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)

__all__ = ("resolve_agent_turn_terminal_defaults",)


def resolve_agent_turn_terminal_defaults(status: str) -> tuple[str, str | None, str | None]:
    if status == AGENT_TURN_STATUS_COMPLETED:
        return (AGENT_TURN_STATUS_COMPLETED, None, None)
    if status == AGENT_TURN_STATUS_MAX_ITERATIONS:
        return (
            AGENT_TURN_STATUS_MAX_ITERATIONS,
            "Agent turn reached max iterations.",
            AGENT_TURN_STATUS_MAX_ITERATIONS,
        )
    if status == AGENT_TURN_STATUS_CANCELLED:
        return (
            AGENT_TURN_STATUS_CANCELLED,
            "Agent turn cancelled.",
            AGENT_TURN_STATUS_CANCELLED,
        )
    if status == AGENT_TURN_STATUS_ERROR:
        return (
            AGENT_TURN_STATUS_ERROR,
            "Agent turn failed.",
            "server_error",
        )
    if status == AGENT_TURN_STATUS_ABANDONED:
        return (
            AGENT_TURN_STATUS_ABANDONED,
            "Agent turn was abandoned before completion.",
            AGENT_TURN_STATUS_ABANDONED,
        )
    return (status, None, None)
