"""SoAI - Async durable power operation repository [backend/database/repositories/system/power_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.system.power_operations import PowerOperation, PowerOperationAction
from core.timing.durations import MILLISECONDS_PER_DAY, MILLISECONDS_PER_HOUR
from core.validation.strict_numbers import require_non_negative_int_strict
from database.repositories.system.power_operation_persistence import (
    sync_cancel_power_operation,
    sync_claim_due_power_operation,
    sync_complete_power_operation,
    sync_fail_power_operation,
    sync_mark_power_dispatch_started,
    sync_reconcile_power_operations,
)
from database.repositories.system.power_operation_records import (
    read_active_power_operation,
    read_power_operation,
    read_power_operation_next_wake,
    sync_accept_power_operation,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol

__all__ = ("DatabasePowerOperations", "POWER_OPERATION_RETENTION_MS")

POWER_OPERATION_RETENTION_MS = 30 * MILLISECONDS_PER_DAY
MAX_POWER_OPERATION_DELAY_MS = 24 * MILLISECONDS_PER_HOUR


class DatabasePowerOperations:
    def __init__(self, core: DatabaseCoreProtocol) -> None:
        self._core = core

    async def accept(
        self,
        *,
        operation_id: str,
        owner_id: int,
        action: PowerOperationAction,
        force: bool,
        delay_ms: int,
        accepted_at_ms: int,
    ) -> PowerOperation:
        normalized_id = require_mutation_request_id(operation_id)
        normalized_owner_id = require_non_negative_int_strict(
            owner_id,
            error_message="Power operation owner ID must be a non-negative integer.",
        )
        normalized_delay_ms = require_non_negative_int_strict(
            delay_ms,
            error_message="Power operation delay must be a non-negative integer.",
        )
        if normalized_delay_ms > MAX_POWER_OPERATION_DELAY_MS:
            raise ValidationError("Power operation delay exceeds 24 hours.")
        normalized_accepted_at_ms = require_non_negative_int_strict(
            accepted_at_ms,
            error_message="Power operation acceptance timestamp must be a non-negative integer.",
        )
        if not isinstance(action, PowerOperationAction):
            raise ValidationError("Power operation action is invalid.")
        if not isinstance(force, bool):
            raise ValidationError("Power operation force must be a boolean.")
        if (
            action
            in {
                PowerOperationAction.APPLICATION_RESTART,
                PowerOperationAction.APPLICATION_SHUTDOWN,
            }
            and force
        ):
            raise ValidationError("Application power operations do not support force.")
        return await self._core.writer.queue_write_operation(
            sync_accept_power_operation,
            normalized_id,
            normalized_owner_id,
            action,
            force,
            normalized_delay_ms,
            normalized_accepted_at_ms,
            normalized_accepted_at_ms - POWER_OPERATION_RETENTION_MS,
        )

    async def get(self, operation_id: str) -> PowerOperation | None:
        normalized_id = require_mutation_request_id(operation_id)
        return await self._core.reader.execute_read(read_power_operation, normalized_id)

    async def get_active(self) -> PowerOperation | None:
        return await self._core.reader.execute_read(read_active_power_operation)

    async def cancel(self, operation_id: str, *, cancelled_at_ms: int) -> PowerOperation:
        normalized_id = require_mutation_request_id(operation_id)
        return await self._core.writer.queue_write_operation(
            sync_cancel_power_operation,
            normalized_id,
            cancelled_at_ms,
        )

    async def claim_due(
        self,
        *,
        now_ms: int,
        claim_owner: str,
        lease_duration_ms: int,
        max_attempts: int,
    ) -> PowerOperation | None:
        return await self._core.writer.queue_write_operation(
            sync_claim_due_power_operation,
            now_ms,
            claim_owner,
            lease_duration_ms,
            max_attempts,
        )

    async def mark_dispatch_started(
        self,
        operation_id: str,
        *,
        claim_owner: str,
        dispatch_started_at_ms: int,
    ) -> PowerOperation:
        return await self._core.writer.queue_write_operation(
            sync_mark_power_dispatch_started,
            require_mutation_request_id(operation_id),
            claim_owner,
            dispatch_started_at_ms,
        )

    async def complete(
        self,
        operation_id: str,
        *,
        claim_owner: str,
        completed_at_ms: int,
        result_code: str,
    ) -> PowerOperation:
        return await self._core.writer.queue_write_operation(
            sync_complete_power_operation,
            require_mutation_request_id(operation_id),
            claim_owner,
            completed_at_ms,
            result_code,
        )

    async def fail(
        self,
        operation_id: str,
        *,
        claim_owner: str,
        completed_at_ms: int,
        error_code: str,
    ) -> PowerOperation:
        return await self._core.writer.queue_write_operation(
            sync_fail_power_operation,
            require_mutation_request_id(operation_id),
            claim_owner,
            completed_at_ms,
            error_code,
        )

    async def reconcile(
        self,
        *,
        now_ms: int,
        max_attempts: int,
    ) -> tuple[PowerOperation, ...]:
        return await self._core.writer.queue_write_operation(
            sync_reconcile_power_operations,
            now_ms,
            max_attempts,
            now_ms - POWER_OPERATION_RETENTION_MS,
        )

    async def next_wake_at_ms(self) -> int | None:
        return await self._core.reader.execute_read(read_power_operation_next_wake)
