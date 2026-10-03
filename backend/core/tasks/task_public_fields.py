"""SoAI - Public terminal task field projection [backend/core/tasks/task_public_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.memory_exhaustion import resolve_memory_exhaustion_message
from core.tasks.enums import TaskStatus
from core.tasks.protocols_serialization import TaskTerminalFieldsProtocol

__all__ = ("PublicTaskTerminalFields", "TaskTerminalFields", "resolve_public_task_terminal_fields")


@dataclass(frozen=True, slots=True)
class TaskTerminalFields:
    status: TaskStatus
    error_code: int | None
    error_type: str | None
    status_message: str | None
    error_message: str | None
    public_error_message: str | None = None


@dataclass(frozen=True, slots=True)
class PublicTaskTerminalFields:
    status_message: str | None
    error_message: str | None


def resolve_public_task_terminal_fields(
    task: TaskTerminalFieldsProtocol,
) -> PublicTaskTerminalFields:
    if task.status != TaskStatus.FAILED:
        return PublicTaskTerminalFields(
            status_message=task.status_message,
            error_message=task.error_message,
        )
    if task.public_error_message is not None:
        return PublicTaskTerminalFields(
            status_message=task.public_error_message,
            error_message=task.public_error_message,
        )
    if task.error_code is not None and 400 <= task.error_code < 500:
        return PublicTaskTerminalFields(
            status_message=task.status_message,
            error_message=task.error_message,
        )
    memory_message = resolve_memory_exhaustion_message(task.error_type)
    if memory_message is not None:
        return PublicTaskTerminalFields(
            status_message=memory_message,
            error_message=memory_message,
        )
    return PublicTaskTerminalFields(
        status_message="Task failed.",
        error_message="Task failed.",
    )
