"""SoAI - Public terminal task field projection [backend/core/tasks/task_public_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.memory_exhaustion import resolve_memory_exhaustion_message
from core.tasks.enums import TaskStatus

__all__ = ("PublicTaskTerminalFields", "resolve_public_task_terminal_fields")


@dataclass(frozen=True, slots=True)
class PublicTaskTerminalFields:
    status_message: str | None
    error_message: str | None


def resolve_public_task_terminal_fields(
    *,
    status: TaskStatus,
    error_code: int | None,
    error_type: str | None,
    status_message: str | None,
    error_message: str | None,
) -> PublicTaskTerminalFields:
    if status != TaskStatus.FAILED:
        return PublicTaskTerminalFields(
            status_message=status_message,
            error_message=error_message,
        )
    if error_code is not None and 400 <= error_code < 500:
        return PublicTaskTerminalFields(
            status_message=status_message,
            error_message=error_message,
        )
    memory_message = resolve_memory_exhaustion_message(error_type)
    if memory_message is not None:
        return PublicTaskTerminalFields(
            status_message=status_message,
            error_message=memory_message,
        )
    return PublicTaskTerminalFields(
        status_message="Task failed.",
        error_message="Task failed.",
    )
