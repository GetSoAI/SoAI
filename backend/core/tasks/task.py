"""SoAI - Task dataclass for async task tracking and lifecycle [backend/core/tasks/task.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.enums import TaskStatus
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task_serialization import build_task_dict, validate_and_normalize_task
from core.tasks.type_catalog import (
    TaskTypeId,
    is_orchestrated_inference_task_type,
)
from core.timing.epoch import epoch_ms
from core.types.dict import FrozenJsonDict, freeze_json_dict
from core.types.pydantic_json_value import coerce_to_pydantic_json_dict

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.types.json import JSONValue

__all__ = ("Task",)


@dataclass(slots=True)
class Task:
    task_id: str
    task_type: TaskTypeId
    status: TaskStatus
    user_id: int
    owner_id: str
    owner_type: str
    cancellation_id: str
    created_at_ms: int = field(default_factory=epoch_ms)
    updated_at_ms: int = field(default_factory=epoch_ms)
    completed_at_ms: int | None = None
    ttl_ms: int | None = None
    poll_interval_ms: int = 1000
    progress_current: int | None = None
    progress_total: int | None = None
    status_message: str | None = None
    progress_details: str | None = None
    metadata: FrozenJsonDict = field(default_factory=FrozenJsonDict.empty, hash=False)
    result: dict[str, JSONValue] | None = field(default=None, hash=False)
    error_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    cancellation_requested_at_ms: int | None = None
    reply_queue: asyncio.Queue[Event] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )
    _last_terminal_progress_percent: int | None = field(default=None, repr=False, compare=False)
    _last_terminal_status_message: str | None = field(default=None, repr=False, compare=False)
    _last_terminal_logged_at: float = field(default=0.0, repr=False, compare=False)
    orchestration_context: OrchestrationContext | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )
    _snapshot_tracking_id: str | None = field(default=None, repr=False, compare=False)
    _snapshot_excluded_universal_ids: frozenset[str] | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    _snapshot_virtual_model_name: str | None = field(default=None, repr=False, compare=False)
    update_counter: int = field(default=0, repr=False, compare=False)
    mutation_admission_outcome: Literal["accepted", "replay"] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @property
    def snapshot_tracking_id(self) -> str | None:
        return self._snapshot_tracking_id

    @property
    def snapshot_excluded_universal_ids(self) -> frozenset[str] | None:
        return self._snapshot_excluded_universal_ids

    @property
    def snapshot_virtual_model_name(self) -> str | None:
        return self._snapshot_virtual_model_name

    @property
    def ttl_expires_at_ms(self) -> int | None:
        if self.ttl_ms is None:
            return None
        base_time = (
            self.completed_at_ms
            if self.completed_at_ms is not None
            else self.updated_at_ms or self.created_at_ms
        )
        return int(base_time) + int(self.ttl_ms)

    def is_expired(self) -> bool:
        if not self.status.is_terminal():
            return False
        expires_ms = self.ttl_expires_at_ms
        return expires_ms is not None and epoch_ms() > int(expires_ms)

    def progress_percent(self) -> float | None:
        if self.progress_total is None or self.progress_total <= 0:
            return None
        if self.progress_current is None:
            return 0.0
        return min(100.0, max(0.0, self.progress_current * 100 / self.progress_total))

    def is_progress_trackable(self) -> bool:
        return self.progress_total is not None and self.progress_total > 0

    def with_reply_queue(self, queue: asyncio.Queue[Event]) -> Task:
        return dataclasses.replace(self, reply_queue=queue)

    def with_mutation_admission_outcome(
        self,
        outcome: Literal["accepted", "replay"],
    ) -> Task:
        return dataclasses.replace(self, mutation_admission_outcome=outcome)

    def require_orchestration_context(self) -> OrchestrationContext:
        context = self.orchestration_context
        if context is None:
            raise StateError("Task is missing orchestration_context")
        return context

    def with_orchestration_context(
        self,
        context: OrchestrationContext,
        *,
        mark_updated: bool = True,
    ) -> Task:
        if not is_orchestrated_inference_task_type(self.task_type):
            raise ValidationError(
                f"Cannot attach orchestration context to task type {self.task_type}",
            )
        if not mark_updated:
            return dataclasses.replace(self, orchestration_context=context)
        return dataclasses.replace(
            self,
            updated_at_ms=epoch_ms(),
            orchestration_context=context,
            update_counter=self.update_counter + 1,
        )

    def is_orchestrated_inference(self) -> bool:
        return self.orchestration_context is not None

    def without_reply_queue(
        self,
    ) -> tuple[Task, asyncio.Queue[Event] | None]:
        return (dataclasses.replace(self, reply_queue=None), self.reply_queue)

    def __post_init__(self) -> None:
        validate_and_normalize_task(self)

    def with_persisted_state(self, persisted: Task) -> Task:
        if self.task_id != persisted.task_id:
            raise ValidationError("Cannot apply persisted state from a different task_id.")
        return dataclasses.replace(
            self,
            task_type=persisted.task_type,
            status=persisted.status,
            user_id=persisted.user_id,
            owner_id=persisted.owner_id,
            owner_type=persisted.owner_type,
            cancellation_id=persisted.cancellation_id,
            created_at_ms=persisted.created_at_ms,
            updated_at_ms=persisted.updated_at_ms,
            completed_at_ms=persisted.completed_at_ms,
            ttl_ms=persisted.ttl_ms,
            poll_interval_ms=persisted.poll_interval_ms,
            progress_current=persisted.progress_current,
            progress_total=persisted.progress_total,
            status_message=persisted.status_message,
            progress_details=persisted.progress_details,
            metadata=persisted.metadata,
            result=persisted.result,
            error_code=persisted.error_code,
            error_type=persisted.error_type,
            error_message=persisted.error_message,
            cancellation_requested_at_ms=persisted.cancellation_requested_at_ms,
            orchestration_context=(
                None
                if persisted.status.is_terminal()
                else (
                    persisted.orchestration_context
                    if self.orchestration_context is None
                    else self.orchestration_context
                )
            ),
            update_counter=max(self.update_counter, persisted.update_counter),
        )

    def to_dict(
        self,
        *,
        include_result: bool = True,
        include_metadata: bool = True,
    ) -> dict[str, JSONValue]:
        return build_task_dict(
            self,
            include_result=include_result,
            include_metadata=include_metadata,
        )

    def snapshot(self) -> Task:
        context = self.orchestration_context
        return Task(
            task_id=self.task_id,
            task_type=self.task_type,
            status=self.status,
            user_id=self.user_id,
            owner_id=self.owner_id,
            owner_type=self.owner_type,
            cancellation_id=self.cancellation_id,
            created_at_ms=self.created_at_ms,
            updated_at_ms=self.updated_at_ms,
            completed_at_ms=self.completed_at_ms,
            ttl_ms=self.ttl_ms,
            poll_interval_ms=self.poll_interval_ms,
            progress_current=self.progress_current,
            progress_total=self.progress_total,
            status_message=self.status_message,
            progress_details=self.progress_details,
            metadata=self.metadata,
            result=self.result,
            error_code=self.error_code,
            error_type=self.error_type,
            error_message=self.error_message,
            cancellation_requested_at_ms=self.cancellation_requested_at_ms,
            reply_queue=None,
            _last_terminal_progress_percent=self._last_terminal_progress_percent,
            _last_terminal_status_message=self._last_terminal_status_message,
            _last_terminal_logged_at=self._last_terminal_logged_at,
            orchestration_context=None,
            _snapshot_tracking_id=context.tracking_id if context else None,
            _snapshot_excluded_universal_ids=(
                frozenset(context.excluded_universal_ids)
                if context and context.excluded_universal_ids
                else None
            ),
            _snapshot_virtual_model_name=(context.virtual_model_name if context else None),
            update_counter=self.update_counter,
        )

    @classmethod
    def create(
        cls,
        task_type: TaskTypeId,
        user_id: int,
        owner_id: str,
        owner_type: str,
        *,
        task_id: str | None = None,
        cancellation_id: str,
        status: TaskStatus = TaskStatus.PENDING,
        status_message: str | None = None,
        ttl_ms: int | None = None,
        poll_interval_ms: int = 1000,
        progress_total: int | None = None,
        metadata: dict[str, JSONValue] | None = None,
        reply_queue: asyncio.Queue[Event] | None = None,
    ) -> Task:
        resolved_task_id = str(task_id or f"task_{uuid.uuid4().hex}").strip()
        if not resolved_task_id:
            raise ValidationError("task_id must be a non-empty string.")
        resolved_cancel_id = require_cancellation_id(cancellation_id)
        coerced_metadata = coerce_to_pydantic_json_dict(metadata) if metadata else {}
        return cls(
            task_id=resolved_task_id,
            task_type=task_type,
            status=status,
            status_message=status_message,
            user_id=user_id,
            owner_id=owner_id,
            owner_type=owner_type,
            cancellation_id=resolved_cancel_id,
            ttl_ms=ttl_ms,
            poll_interval_ms=poll_interval_ms,
            progress_total=progress_total,
            progress_current=0 if progress_total is not None else None,
            metadata=freeze_json_dict(coerced_metadata),
            reply_queue=reply_queue,
        )
