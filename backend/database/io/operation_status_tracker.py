"""SoAI - Database operation status tracking [backend/database/io/operation_status_tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar

from database.io.internal_protocols import (
    DatabaseWriteJobProtocol,
    OperationCompletionRecord,
    OperationStatus,
)

__all__ = ("OperationStatusTracker",)


@dataclass(slots=True)
class OperationStatusTracker:
    ttl_sec: float = 300.0
    max_entries: int = 10_000
    _status: dict[str, OperationCompletionRecord] = field(
        default_factory=dict[str, OperationCompletionRecord],
    )
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _active_jobs: dict[str, DatabaseWriteJobProtocol] = field(
        default_factory=dict[str, DatabaseWriteJobProtocol],
    )
    _acknowledged_operation_ids: set[str] = field(default_factory=set[str])
    _terminal_statuses: ClassVar[frozenset[OperationStatus]] = frozenset(
        {
            OperationStatus.COMMITTED,
            OperationStatus.FAILED,
            OperationStatus.SKIPPED,
            OperationStatus.OUTCOME_UNKNOWN,
        },
    )

    def _is_terminal_status(self, status: OperationStatus) -> bool:
        return status in self._terminal_statuses

    def record(
        self,
        operation_id: str,
        status: OperationStatus,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            self._status[operation_id] = OperationCompletionRecord(
                operation_id=operation_id,
                status=status,
                completed_at=time.monotonic(),
                error_type=error_type,
            )

    def record_if_not_terminal(
        self,
        operation_id: str,
        status: OperationStatus,
        error_type: str | None = None,
    ) -> bool:
        with self._lock:
            record = self._status.get(operation_id)
            if record is not None and self._is_terminal_status(record.status):
                return False
            self._status[operation_id] = OperationCompletionRecord(
                operation_id=operation_id,
                status=status,
                completed_at=time.monotonic(),
                error_type=error_type,
            )
            return True

    def get_status(self, operation_id: str) -> OperationStatus | None:
        with self._lock:
            record = self._status.get(operation_id)
            return record.status if record else None

    def unregister_active_job(self, operation_id: str) -> None:
        with self._lock:
            self._active_jobs.pop(operation_id, None)

    def pop_active_jobs(self) -> list[tuple[str, DatabaseWriteJobProtocol]]:
        with self._lock:
            active_jobs = list(self._active_jobs.items())
            self._active_jobs.clear()
            return active_jobs

    def mark_acknowledged(self, operation_id: str) -> None:
        with self._lock:
            self._acknowledged_operation_ids.add(operation_id)

    def snapshot_acknowledged_operation_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._acknowledged_operation_ids))

    def confirm_acknowledged_operation_ids(self, operation_ids: tuple[str, ...]) -> None:
        with self._lock:
            for operation_id in operation_ids:
                self._acknowledged_operation_ids.discard(operation_id)

    def claim_for_execution(
        self,
        operation_id: str,
        job: DatabaseWriteJobProtocol,
    ) -> bool:
        with self._lock:
            record = self._status.get(operation_id)
            if record is None:
                self._status[operation_id] = OperationCompletionRecord(
                    operation_id=operation_id,
                    status=OperationStatus.EXECUTING,
                    completed_at=time.monotonic(),
                )
                self._active_jobs[operation_id] = job
                return True

            if record.status is not OperationStatus.PENDING:
                return False

            self._status[operation_id] = OperationCompletionRecord(
                operation_id=operation_id,
                status=OperationStatus.EXECUTING,
                completed_at=time.monotonic(),
                error_type=record.error_type,
            )
            self._active_jobs[operation_id] = job
            return True

    def prune(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired_ids = [
                op_id
                for op_id, record in self._status.items()
                if self._is_terminal_status(record.status)
                and (now - record.completed_at) > self.ttl_sec
            ]
            for op_id in expired_ids:
                del self._status[op_id]

            if len(self._status) <= self.max_entries:
                return

            terminal_entries = [
                (op_id, record)
                for op_id, record in self._status.items()
                if self._is_terminal_status(record.status)
            ]
            if not terminal_entries:
                return

            sorted_terminal_entries = sorted(
                terminal_entries,
                key=lambda item: item[1].completed_at,
            )
            non_terminal_entries = len(self._status) - len(terminal_entries)
            allowed_terminal_entries = max(self.max_entries - non_terminal_entries, 0)
            excess = len(terminal_entries) - allowed_terminal_entries
            if excess <= 0:
                return
            for op_id, _ in sorted_terminal_entries[:excess]:
                del self._status[op_id]
