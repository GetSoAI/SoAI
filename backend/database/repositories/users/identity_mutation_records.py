"""SoAI - Durable identity mutation repository [backend/database/repositories/users/identity_mutation_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import time

import aiosqlite

from core.errors.exceptions import ConflictError, DatabaseError
from core.users.identity_mutation_records import (
    IdentityMutationBinding,
    IdentityMutationRecord,
)
from core.users.password_change import (
    PasswordChangeDatabaseResult,
    PasswordChangeTransaction,
)
from core.users.username_rename import (
    UsernameRenameDatabaseResult,
    UsernameRenameTransaction,
)
from database.core.query_execution import query_one_to_dict
from database.repositories.dependencies import DatabaseRepositoryDependencies
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.identity_mutation_record_storage import (
    identity_mutation_binding_matches,
    identity_mutation_record_from_row,
    sync_finalize_identity_mutation_absence,
    sync_insert_failed_identity_mutation,
)
from database.repositories.users.user_password_updates import sync_change_user_password
from database.repositories.users.username_rename_transaction import sync_rename_username
from database.repositories.users.webui_identity_maintenance import (
    sync_maintain_webui_identity_state,
)
from database.repositories.users.webui_session_registration import (
    raise_classified_webui_session_registration_error,
)


class DatabaseUserMutations:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core

    async def maintain_identity_state(self) -> None:
        await self.core.writer.queue_write_operation(
            sync_maintain_webui_identity_state,
        )

    async def read(self, binding: IdentityMutationBinding) -> IdentityMutationRecord | None:
        async def query(database: aiosqlite.Connection) -> IdentityMutationRecord | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT * FROM webui_user_mutations
                WHERE actor_user_id = ? AND operation_id = ?
                """,
                (binding.actor_user_id, binding.operation_id),
            )
            if row is None:
                return None
            record = identity_mutation_record_from_row(row)
            if not identity_mutation_binding_matches(record, binding):
                raise ConflictError("Mutation operation ID is bound to different input.")
            return record

        return await self.core.reader.execute_read(query)

    async def read_by_actor_operation(
        self,
        actor_user_id: int,
        operation_id: str,
    ) -> IdentityMutationRecord | None:
        async def query(database: aiosqlite.Connection) -> IdentityMutationRecord | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT * FROM webui_user_mutations
                WHERE actor_user_id = ? AND operation_id = ?
                """,
                (actor_user_id, operation_id),
            )
            return identity_mutation_record_from_row(row) if row is not None else None

        return await self.core.reader.execute_read(query)

    async def finalize_absence(
        self,
        binding: IdentityMutationBinding,
    ) -> IdentityMutationRecord | None:
        return await self.core.writer.queue_write_operation(
            sync_finalize_identity_mutation_absence,
            binding,
        )

    async def record_failure(
        self,
        binding: IdentityMutationBinding,
        *,
        error_code: str,
        trace_id: str | None,
    ) -> IdentityMutationRecord:
        return await self.core.writer.queue_write_operation(
            sync_insert_failed_identity_mutation,
            binding,
            error_code,
            trace_id,
        )

    async def rename_username(
        self,
        transaction: UsernameRenameTransaction,
    ) -> UsernameRenameDatabaseResult:
        remaining_seconds = transaction.deadline_monotonic - time.monotonic()
        if remaining_seconds <= 0:
            return UsernameRenameDatabaseResult(
                record=await self.record_failure(
                    transaction.binding,
                    error_code="identity_mutation_deadline_exceeded",
                    trace_id=None,
                ),
                revoked_jtis=(),
                committed_now=False,
            )
        try:
            result = await self.core.writer.queue_write_operation(
                sync_rename_username,
                transaction,
                enqueue_timeout=remaining_seconds,
                operation_timeout=remaining_seconds,
            )
        except (sqlite3.IntegrityError, DatabaseError) as exception:
            raise_classified_webui_session_registration_error(exception)
        if result.committed_now:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def change_password(
        self,
        transaction: PasswordChangeTransaction,
    ) -> PasswordChangeDatabaseResult:
        remaining_seconds = transaction.deadline_monotonic - time.monotonic()
        if remaining_seconds <= 0:
            return PasswordChangeDatabaseResult(
                record=await self.record_failure(
                    transaction.binding,
                    error_code="identity_mutation_deadline_exceeded",
                    trace_id=None,
                ),
                revoked_jtis=(),
                user=None,
                committed_now=False,
            )
        try:
            result = await self.core.writer.queue_write_operation(
                sync_change_user_password,
                transaction,
                enqueue_timeout=remaining_seconds,
                operation_timeout=remaining_seconds,
            )
        except (sqlite3.IntegrityError, DatabaseError) as exception:
            raise_classified_webui_session_registration_error(exception)
        if result.committed_now:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result


__all__ = ("DatabaseUserMutations",)
