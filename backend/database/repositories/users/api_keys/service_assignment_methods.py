"""SoAI - API key repository assignment and usage methods [backend/database/repositories/users/api_keys/service_assignment_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.auth.api_key_assignment import APIKeyAssignmentOutcome
from core.errors.exceptions import DatabaseError
from core.timing.epoch import epoch_ms
from database.core.flags import FEATURE_AUTH
from database.repositories.users.api_key_quota_usage_windows.finalization import (
    sync_finalize_quota_reservation,
)
from database.repositories.users.api_key_quota_usage_windows.reconciliation import (
    sync_reconcile_expired_quota_reservations,
)
from database.repositories.users.api_key_row_normalization import sanitize_api_key_row
from database.repositories.users.api_keys.assignment_ops import (
    get_active_key_id_for_user,
    sync_assign_user_to_key,
    sync_unassign_user_from_key,
)
from database.repositories.users.api_keys.internal_protocols import (
    DatabaseAPIKeysServiceProtocol,
)
from database.repositories.users.api_keys.quota_error_propagation import (
    raise_database_cause_if_needed,
)
from database.repositories.users.api_keys.write_ops import (
    sync_delete_all_keys,
    sync_delete_key,
    sync_record_usage,
    sync_revoke_key,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "assign_user_to_key_method",
    "delete_all_keys_method",
    "delete_key_method",
    "finalize_quota_reservation_method",
    "get_active_key_id_for_user_method",
    "reconcile_quota_reservations_method",
    "record_usage_method",
    "revoke_key_method",
    "unassign_user_from_key_method",
)


async def record_usage_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
    client_ip: str | None,
    timestamp: int | None = None,
) -> None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    await self.core.writer.queue_write_operation(
        sync_record_usage,
        key_id,
        epoch_ms() if timestamp is None else int(timestamp),
        client_ip,
    )


async def revoke_key_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
    revoked_by: int | None,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_revoke_key,
        key_id,
        revoked_by,
        epoch_ms(),
        self.cryptor.decrypt_hash,
    )
    return sanitize_api_key_row(row)


async def delete_key_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
) -> tuple[int, int]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await self.core.writer.queue_write_operation(
        sync_delete_key,
        key_id,
    )


async def delete_all_keys_method(
    self: DatabaseAPIKeysServiceProtocol,
) -> tuple[int, int]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await self.core.writer.queue_write_operation(
        sync_delete_all_keys,
    )


async def get_active_key_id_for_user_method(
    self: DatabaseAPIKeysServiceProtocol,
    user_id: int,
) -> str | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_active_key_id_for_user(self.core, int(user_id), now_ms=epoch_ms())


async def assign_user_to_key_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
    user_id: int,
) -> APIKeyAssignmentOutcome:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await self.core.writer.queue_write_operation(
        sync_assign_user_to_key,
        key_id,
        int(user_id),
    )


async def unassign_user_from_key_method(self: DatabaseAPIKeysServiceProtocol, key_id: str) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await self.core.writer.queue_write_operation(
        sync_unassign_user_from_key,
        key_id,
    )


async def reconcile_quota_reservations_method(
    self: DatabaseAPIKeysServiceProtocol,
    now_ts: int,
    *,
    batch_limit: int = 200,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    try:
        return await self.core.writer.queue_write_operation(
            sync_reconcile_expired_quota_reservations,
            int(now_ts),
            int(batch_limit),
        )
    except DatabaseError as exception:
        raise_database_cause_if_needed(exception)


async def finalize_quota_reservation_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
    reservation: JSONDict,
    actual_units: int,
    now_ts: int,
) -> None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    try:
        await self.core.writer.queue_write_operation(
            sync_finalize_quota_reservation,
            key_id,
            reservation,
            int(actual_units),
            int(now_ts),
        )
    except DatabaseError as exception:
        raise_database_cause_if_needed(exception)
