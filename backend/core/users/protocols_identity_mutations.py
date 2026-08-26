"""SoAI - Identity mutation database protocol [backend/core/users/protocols_identity_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.users.identity_mutation_records import (
    IdentityMutationBinding,
    IdentityMutationRecord,
)
from core.users.password_change import PasswordChangeDatabaseResult, PasswordChangeTransaction
from core.users.username_rename import (
    UsernameRenameDatabaseResult,
    UsernameRenameTransaction,
)


class DatabaseUserMutationsProtocol(Protocol):
    async def read_by_actor_operation(
        self,
        actor_user_id: int,
        operation_id: str,
    ) -> IdentityMutationRecord | None: ...
    async def read(self, binding: IdentityMutationBinding) -> IdentityMutationRecord | None: ...
    async def finalize_absence(
        self,
        binding: IdentityMutationBinding,
    ) -> IdentityMutationRecord | None: ...
    async def record_failure(
        self,
        binding: IdentityMutationBinding,
        *,
        error_code: str,
        trace_id: str | None,
    ) -> IdentityMutationRecord: ...
    async def rename_username(
        self,
        transaction: UsernameRenameTransaction,
    ) -> UsernameRenameDatabaseResult: ...
    async def change_password(
        self,
        transaction: PasswordChangeTransaction,
    ) -> PasswordChangeDatabaseResult: ...


__all__ = ("DatabaseUserMutationsProtocol",)
