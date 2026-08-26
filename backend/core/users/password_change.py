"""SoAI - Password change transaction values [backend/core/users/password_change.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.auth.jwt_claims import AccessTokenRecord
from core.auth.webui_sessions import WebuiSessionDescriptor
from core.types.json import JSONDict
from core.users.identity_mutation_records import IdentityMutationBinding, IdentityMutationRecord
from core.users.username_rename import UserIdentitySnapshot


@dataclass(frozen=True, slots=True)
class PasswordChangeTransaction:
    binding: IdentityMutationBinding
    actor: UserIdentitySnapshot
    target: UserIdentitySnapshot
    source_jti: str
    new_hashed_password: str
    deadline_monotonic: float
    recovery_horizon_at_ms: int
    successor: AccessTokenRecord | None
    source_descriptor: WebuiSessionDescriptor | None


@dataclass(frozen=True, slots=True)
class PasswordChangeDatabaseResult:
    record: IdentityMutationRecord
    revoked_jtis: tuple[str, ...]
    user: JSONDict | None
    committed_now: bool


__all__ = ("PasswordChangeDatabaseResult", "PasswordChangeTransaction")
