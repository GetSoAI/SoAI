"""SoAI - Background shell owned-task terminal status mapping [backend/mcp/tools/shell_background/owned_task_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.tool_calls.status_values import TOOL_CALL_STATUS_COMPLETED

__all__ = ("ShellBackgroundOwnedTaskTerminalStatus", "resolve_owned_task_terminal_status")


@dataclass(frozen=True, slots=True)
class ShellBackgroundOwnedTaskTerminalStatus:
    status_message: str
    error_message: str | None


def resolve_owned_task_terminal_status(final_status: str) -> ShellBackgroundOwnedTaskTerminalStatus:
    if final_status == TOOL_CALL_STATUS_COMPLETED:
        return ShellBackgroundOwnedTaskTerminalStatus(
            status_message="Completed",
            error_message=None,
        )
    return ShellBackgroundOwnedTaskTerminalStatus(
        status_message="Failed",
        error_message="Background shell failed.",
    )
