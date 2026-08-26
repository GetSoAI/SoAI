"""SoAI - Typed durable identity mutation records [backend/core/users/identity_mutation_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.users.identity_mutation_contract import (
        IdentityMutationStatus,
        IdentityMutationType,
    )


@dataclass(frozen=True, slots=True)
class IdentityMutationBinding:
    actor_user_id: int
    operation_id: str
    operation_type: IdentityMutationType
    target_user_id: int
    requested_username: str | None


@dataclass(frozen=True, slots=True)
class IdentityMutationRecord:
    binding: IdentityMutationBinding
    status: IdentityMutationStatus
    completed_at_ms: int
    retain_until_ms: int
    error_code: str | None
    trace_id: str | None
    previous_username: str | None
    new_username: str | None
    new_identity_revision: int | None
    previous_password_revision: int | None
    new_password_revision: int | None


__all__ = ("IdentityMutationBinding", "IdentityMutationRecord")
