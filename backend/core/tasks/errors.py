"""SoAI - Task-related error types [backend/core/tasks/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.errors.exceptions import ApiError, ConcurrencyError, DatabaseError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "TASK_STATE_PERSISTENCE_FAILED_MESSAGE",
    "TaskFinalizationPersistenceError",
    "TaskIDCollisionError",
    "MutationAdmissionConflictError",
)

TASK_STATE_PERSISTENCE_FAILED_MESSAGE = "Task state persistence failed."


class MutationAdmissionConflictError(ApiError):
    def __init__(self, task_id: str | None) -> None:
        self.task_id = task_id
        super().__init__(
            "A conflicting mutation is already active.",
            code="mutation_conflict",
            http_status=409,
            details={"task_id": task_id} if task_id else None,
        )


class TaskFinalizationPersistenceError(DatabaseError):
    __slots__ = ()


class TaskIDCollisionError(ConcurrencyError):

    def __init__(self, task_id: str, existing_status: str) -> None:
        self.task_id = task_id
        self.existing_status = existing_status
        super().__init__(f"Task with ID {task_id} already exists (status: {existing_status})")

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.task_id, self.existing_status), {})
