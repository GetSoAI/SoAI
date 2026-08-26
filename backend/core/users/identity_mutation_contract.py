"""SoAI - Durable identity mutation contract [backend/core/users/identity_mutation_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from typing import Literal

    type IdentityMutationType = Literal["username_rename", "password_change"]
    type IdentityMutationStatus = Literal["committed", "failed"]

IDENTITY_MUTATION_DEADLINE_MS = 30_000
SESSION_ROTATION_POST_COMMIT_MIN_MS = 60_000
IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS = 5_000
IDENTITY_MUTATION_FINAL_PROBE_MS = 5_000
SESSION_LINEAGE_PRUNE_GRACE_MS = 30_000
USER_MUTATION_RESULT_MIN_RETENTION_MS = 86_400_000
IDENTITY_MUTATION_CLIENT_RECOVERY_MS = (
    IDENTITY_MUTATION_DEADLINE_MS
    + SESSION_ROTATION_POST_COMMIT_MIN_MS
    + IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS
)
IDENTITY_MUTATION_SERVER_HORIZON_MS = (
    IDENTITY_MUTATION_CLIENT_RECOVERY_MS + IDENTITY_MUTATION_FINAL_PROBE_MS
)
IDENTITY_MUTATION_TYPES: tuple[IdentityMutationType, ...] = (
    "username_rename",
    "password_change",
)
IDENTITY_MUTATION_STATUSES: tuple[IdentityMutationStatus, ...] = (
    "committed",
    "failed",
)
IDENTITY_MUTATION_FAILURE_CODES = (
    "incorrect_current_password",
    "username_unchanged",
    "username_conflict",
    "operation_id_conflict",
    "user_state_conflict",
    "identity_mutation_deadline_exceeded",
    "identity_mutation_cancelled",
    "identity_mutation_not_committed",
    "identity_mutation_time_invalid",
    "identity_mutation_session_collision",
    "identity_mutation_failed",
    "session_rotation_window_unavailable",
)


def sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def require_identity_mutation_type(value: str) -> IdentityMutationType:
    if value == "username_rename":
        return "username_rename"
    if value == "password_change":
        return "password_change"
    raise ValidationError("Identity mutation type is invalid.")


def require_identity_mutation_status(value: str) -> IdentityMutationStatus:
    if value == "committed":
        return "committed"
    if value == "failed":
        return "failed"
    raise ValidationError("Identity mutation status is invalid.")


__all__ = (
    "IDENTITY_MUTATION_CLIENT_RECOVERY_MS",
    "IDENTITY_MUTATION_DEADLINE_MS",
    "IDENTITY_MUTATION_FAILURE_CODES",
    "IDENTITY_MUTATION_FINAL_PROBE_MS",
    "IDENTITY_MUTATION_NETWORK_ALLOWANCE_MS",
    "IDENTITY_MUTATION_SERVER_HORIZON_MS",
    "IDENTITY_MUTATION_STATUSES",
    "IDENTITY_MUTATION_TYPES",
    "SESSION_LINEAGE_PRUNE_GRACE_MS",
    "SESSION_ROTATION_POST_COMMIT_MIN_MS",
    "USER_MUTATION_RESULT_MIN_RETENTION_MS",
    "require_identity_mutation_status",
    "require_identity_mutation_type",
    "sql_values",
)
