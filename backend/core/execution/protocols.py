"""SoAI - Shared execution ownership and snapshot contracts [backend/core/execution/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryLifecycleView, TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AgentTurnSnapshot",
    "AutomationRunSnapshot",
    "OwnedExecutionCancellationProtocol",
    "OwnedExecutionCore",
    "OwnedExecutionFinalizerProtocol",
    "OwnedExecutionSnapshotLoaderProtocol",
    "OwnedExecutionSnapshotProtocol",
    "OwnedExecutionTaskCreatorProtocol",
    "OwnedExecutionWaiterProtocol",
    "SubagentSnapshot",
)


@dataclass(frozen=True, slots=True)
class OwnedExecutionCore:
    execution_type: str
    owner_task_id: str | None
    status: str
    status_message: str | None
    started_at_ms: int
    updated_at_ms: int
    finished_at_ms: int | None
    requested_model: str | None
    token_usage: JSONDict | None


@dataclass(frozen=True, slots=True)
class SubagentSnapshot(OwnedExecutionCore):
    subagent_id: str
    mode: str
    display_name: str | None
    conv_id: str
    parent_turn_id: str
    parent_tool_call_id: str
    parent_iteration_index: int
    result_text: str | None
    error_message: str | None
    error_type: str | None


@dataclass(frozen=True, slots=True)
class AgentTurnIdentityFields:
    conv_id: str
    user_id: int
    turn_id: str
    turn_scope: str
    parent_turn_id: str | None
    parent_tool_call_id: str | None
    parent_iteration_index: int | None
    display_name: str | None


@dataclass(frozen=True, slots=True)
class AgentTurnSnapshot(OwnedExecutionCore):
    conv_id: str
    user_id: int
    turn_id: str
    turn_scope: str
    parent_turn_id: str | None
    parent_tool_call_id: str | None
    parent_iteration_index: int | None
    display_name: str | None
    execution_token: str
    server_boot_id: str
    mode: str
    max_iterations: int
    iteration_index: int
    sequence: int
    turn_cancellation_id: str | None
    active_inference_cancellation_id: str | None
    assistant_text: str | None
    tool_calls: list[JSONDict]
    tool_results: list[JSONValue]
    activities: list[JSONDict]
    reached_max_iterations: bool
    error_message: str | None
    error_type: str | None
    todo_revision: int
    todo_explanation: str | None
    todo: list[dict[str, JSONValue]]


@dataclass(frozen=True, slots=True)
class AutomationRunSnapshot(OwnedExecutionCore):
    run_id: str
    automation_id: str
    user_id: int
    scheduled_at_ms: int
    started_at_actual_ms: int | None
    conv_id: str | None
    result_excerpt: str | None
    title: str | None
    enabled: bool | None
    color: str | None
    turns_snapshot: list[str]
    model_settings_snapshot: JSONDict
    limits_snapshot: JSONDict


class OwnedExecutionSnapshotProtocol(Protocol):
    @property
    def owner_task_id(self) -> str | None: ...

    @property
    def status(self) -> str: ...


class OwnedExecutionTaskCreatorProtocol(Protocol):
    async def __call__(
        self,
        task_registry: TaskRegistryProtocol,
        *,
        user_id: int,
        owner_id: str,
        owner_type: str,
        cancellation_id: str,
        owner_task_id: str | None,
        initial_status: str,
        status_message: str,
        metadata: JSONDict | None,
    ) -> Task: ...


class OwnedExecutionSnapshotLoaderProtocol[SnapshotT](Protocol):
    async def __call__(self) -> SnapshotT | None: ...


class OwnedExecutionWaiterProtocol[SnapshotT](Protocol):
    async def __call__(
        self,
        task_registry: TaskRegistryProtocol,
        *,
        snapshot: SnapshotT | None,
        owner_task_id: str | None,
        timeout_ms: int | None,
        can_wait: Callable[[SnapshotT], bool],
        reload_snapshot: Callable[[], Awaitable[SnapshotT | None]],
    ) -> SnapshotT | None: ...


class OwnedExecutionCancellationProtocol(Protocol):
    async def __call__(
        self,
        registry: TaskRegistryLifecycleView,
        owner_task_id: str,
        reason: str,
        *,
        context: RequestContext | None,
    ) -> Task | None: ...


class OwnedExecutionFinalizerProtocol(Protocol):
    async def __call__(
        self,
        registry: TaskRegistryLifecycleView,
        owner_task_id: str,
        *,
        final_status: str,
        status_message: str,
        error_message: str | None,
        result: dict[str, JSONValue] | None,
    ) -> Task | None: ...
