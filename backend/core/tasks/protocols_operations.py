"""SoAI - Task operation callable protocols [backend/core/tasks/protocols_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

from core.errors.error_types import ErrorType
from core.events.types_base import Event
from core.events.types_plugins import ErrorEvent
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryLifecycleView, TaskRegistryProtocol
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
    from core.tasks.task import Task
    from core.tasks.ttl import TTLMillis
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CreateStreamingTaskCallable",
    "SendErrorEventCallable",
    "SendTaskCompleteEventCallable",
    "SendTaskProgressEventCallable",
    "TaskRegistryCancelCallable",
    "TaskRegistryCreateCallable",
    "TaskRegistryFinalizeCallable",
    "TaskRegistryUpdateStatusCallable",
)


class SendErrorEventCallable(Protocol):
    async def __call__(
        self,
        reply_channel: asyncio.Queue[Event] | None,
        message: str,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
        *,
        context: RequestContext | None = None,
    ) -> ErrorEvent: ...


class SendTaskCompleteEventCallable(Protocol):
    async def __call__(
        self,
        reply_channel: asyncio.Queue[Event] | None,
        message: str,
        *,
        registry: TaskRegistryLifecycleView | None,
        success: bool = True,
        task_id: str | None = None,
        user_id: int | None = None,
        result: JSONDict | None = None,
        cancelled: bool = False,
        error_code: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        mutation_fencing_token: int | None = None,
    ) -> TaskCompleteEvent | None: ...


class SendTaskProgressEventCallable(Protocol):
    async def __call__(
        self,
        reply_channel: asyncio.Queue[Event] | None,
        *,
        registry: TaskRegistryLifecycleView | None,
        percent: int,
        message: str,
        details: JSONValue | None = None,
        task_id: str | None = None,
        user_id: int | None = None,
    ) -> TaskProgressEvent | None: ...


class TaskRegistryCreateCallable(Protocol):
    async def __call__(
        self,
        registry: TaskRegistryProtocol,
        task_type: TaskTypeId,
        user_id: int,
        owner_id: str,
        owner_type: str,
        *,
        task_id: str | None = None,
        cancellation_id: str,
        status: TaskStatus = ...,
        status_message: str | None = None,
        ttl_ms: TTLMillis = ...,
        poll_interval_ms: int = 1000,
        progress_total: int | None = None,
        metadata: JSONDict | None = None,
        reply_queue: asyncio.Queue[Event] | None = None,
        request_source: RequestSource | None = None,
        delivery_mode: str | None = None,
    ) -> Task: ...


class TaskRegistryCancelCallable(Protocol):
    async def __call__(
        self,
        registry: TaskRegistryProtocol,
        task_id: str,
        reason: str = "Cancelled by user",
        *,
        context: RequestContext | None = None,
        mutation_fencing_token: int | None = None,
    ) -> Task | None: ...


class TaskRegistryFinalizeCallable(Protocol):
    async def __call__(
        self,
        registry: TaskRegistryProtocol,
        task_id: str,
        status: TaskStatus,
        *,
        result: Mapping[str, JSONValue] | None = None,
        error_code: int | None = None,
        error_message: str | None = None,
        status_message: str | None = None,
        emit_reply_completion_event: bool = True,
        mutation_fencing_token: int | None = None,
    ) -> Task | None: ...


class TaskRegistryUpdateStatusCallable(Protocol):
    async def __call__(
        self,
        registry: TaskRegistryProtocol,
        task_id: str,
        new_status: TaskStatus,
        *,
        status_message: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
        infer_working_status: bool = False,
    ) -> Task | None: ...


class CreateStreamingTaskCallable(Protocol):
    async def __call__(
        self,
        registry: TaskRegistryProtocol,
        task_type: TaskTypeId,
        user_id: int,
        owner_id: str,
        owner_type: str,
        *,
        task_id: str | None = None,
        cancellation_id: str,
        metadata: JSONDict | None = None,
        ttl_ms: TTLMillis = ...,
        poll_interval_ms: int = 1000,
        progress_total: int | None = None,
        status_message: str | None = None,
        queue_maxsize: int = 1000,
        initial_status: TaskStatus = ...,
        request_source: RequestSource | None = None,
        delivery_mode: str | None = None,
    ) -> tuple[Task, asyncio.Queue[Event]]: ...
