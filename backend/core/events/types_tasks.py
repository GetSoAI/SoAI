"""SoAI - Task-related events and commands [backend/core/events/types_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from core.events.types_base import Event, ReplyableUserCommand, UserCommand
from core.runtime.protocols import RequestContextProtocol
from core.types.json import JSONValue

__all__ = (
    "CancelAllTasksCommand",
    "CancelTaskCommand",
    "MutationDispatchRequestedEvent",
    "TaskCompleteEvent",
    "TaskCreatedEvent",
    "TaskProgressEvent",
    "TaskStatusChangedEvent",
)


@dataclass(slots=True)
class MutationDispatchRequestedEvent(Event): ...


@dataclass(slots=True)
class TaskProgressEvent(Event):
    percent: int
    message: str
    details: str = ""
    task_id: str | None = None
    user_id: int | None = None


@dataclass(slots=True)
class TaskCompleteEvent(Event):
    success: bool
    message: str
    task_id: str | None = None
    user_id: int | None = None
    status: str | None = None
    error_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class TaskCreatedEvent(Event):
    task_id: str
    task_type: str
    owner_id: str
    owner_type: str
    user_id: int = 0
    status: str = "pending"
    status_message: str | None = None
    metadata: Mapping[str, JSONValue] = field(default_factory=dict[str, JSONValue])
    progress_current: int | None = None
    progress_total: int | None = None


@dataclass(slots=True)
class TaskStatusChangedEvent(Event):
    task_id: str
    old_status: str
    new_status: str
    owner_id: str
    user_id: int = 0
    status_message: str | None = None


@dataclass(slots=True)
class CancelTaskCommand(UserCommand):
    cancellation_id: str
    reason: str = "Task cancelled by client or timeout"
    context: RequestContextProtocol | None = None


@dataclass(slots=True)
class CancelAllTasksCommand(ReplyableUserCommand):
    reason: str
    include_internal: bool = False
    context: RequestContextProtocol | None = None
