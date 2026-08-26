"""SoAI - Username rename transaction values [backend/core/users/username_rename.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.auth.jwt_claims import AccessTokenRecord
from core.auth.webui_sessions import WebuiSessionDescriptor
from core.errors.exceptions import StateError
from core.types.json import JSONDict
from core.users.identity_mutation_records import (
    IdentityMutationBinding,
    IdentityMutationRecord,
)
from core.users.user_id import require_strict_user_id
from core.validation.integers import is_strict_int


@dataclass(frozen=True, slots=True)
class UserIdentitySnapshot:
    user_id: int
    username: str
    is_admin: bool
    workspace_path: str
    default_workspace_path: str
    identity_revision: int
    hashed_password: str
    password_revision: int
    password_changed_at_ms: int


@dataclass(frozen=True, slots=True)
class UsernameRenameTransaction:
    binding: IdentityMutationBinding
    actor: UserIdentitySnapshot
    target: UserIdentitySnapshot
    source_jti: str
    deadline_monotonic: float
    recovery_horizon_at_ms: int
    successor: AccessTokenRecord | None
    source_descriptor: WebuiSessionDescriptor | None


@dataclass(frozen=True, slots=True)
class UsernameRenameDatabaseResult:
    record: IdentityMutationRecord
    revoked_jtis: tuple[str, ...]
    committed_now: bool


def user_identity_snapshot_from_record(user: JSONDict) -> UserIdentitySnapshot:
    required_strings = (
        "username",
        "workspace_path",
        "default_workspace_path",
        "hashed_password",
    )
    values: dict[str, str] = {}
    for field_name in required_strings:
        value = user.get(field_name)
        if not isinstance(value, str) or not value:
            raise StateError("User identity snapshot is incomplete.")
        values[field_name] = value
    identity_revision = user.get("identity_revision")
    password_revision = user.get("password_revision")
    password_changed_at_ms = user.get("password_changed_at_ms")
    if (
        not is_strict_int(identity_revision)
        or not is_strict_int(password_revision)
        or not is_strict_int(password_changed_at_ms)
    ):
        raise StateError("User identity snapshot revisions are invalid.")
    return UserIdentitySnapshot(
        user_id=require_strict_user_id(user.get("id")),
        username=values["username"],
        is_admin=bool(user.get("is_admin")),
        workspace_path=values["workspace_path"],
        default_workspace_path=values["default_workspace_path"],
        identity_revision=int(identity_revision),
        hashed_password=values["hashed_password"],
        password_revision=int(password_revision),
        password_changed_at_ms=int(password_changed_at_ms),
    )


__all__ = (
    "UserIdentitySnapshot",
    "UsernameRenameDatabaseResult",
    "UsernameRenameTransaction",
    "user_identity_snapshot_from_record",
)
