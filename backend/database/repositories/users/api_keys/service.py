"""SoAI - Database repository for OpenAI API key management [backend/database/repositories/users/api_keys/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from core.auth.api_key_assignment import APIKeyAssignmentOutcome
from core.auth.openai_protection import OpenAIProtectionState
from core.database.requests import InsertAPIKeyRequest
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.state.errors import DatabaseTimeoutError
from core.types.json import JSONDict
from database.repositories.users.api_keys.protection_state import (
    OpenAIProtectionStateTracker,
)
from database.repositories.users.api_keys.read_ops import count_configured_keys
from database.repositories.users.api_keys.service_assignment_methods import (
    assign_user_to_key_method,
    delete_all_keys_method,
    delete_key_method,
    finalize_quota_reservation_method,
    get_active_key_id_for_user_method,
    reconcile_quota_reservations_method,
    record_usage_method,
    revoke_key_method,
    unassign_user_from_key_method,
)
from database.repositories.users.api_keys.service_dependencies import (
    DatabaseAPIKeysDependencies,
)
from database.repositories.users.api_keys.service_key_methods import (
    count_active_keys_method,
    count_non_revoked_keys_without_expiration_method,
    get_active_key_by_fingerprints_method,
    get_key_by_fingerprints_method,
    get_key_by_id_method,
    has_any_active_key_method,
    insert_key_method,
    list_keys_method,
)
from database.repositories.users.api_keys.service_quota_methods import (
    get_quota_config_method,
    get_quota_status_method,
    reserve_quota_units_for_mode_method,
    set_quota_config_method,
)
from database.repositories.users.bearer_token_hash_crypto import BearerTokenHashCryptor

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.config.protocols import ConfigProtocol
    from core.database.protocols import DatabaseCoreProtocol

__all__ = ("DatabaseAPIKeys",)


class DatabaseAPIKeys:
    @staticmethod
    async def initialize_from_database(
        *,
        core: DatabaseCoreProtocol,
        config: ConfigProtocol,
        fernet: tuple[Fernet, ...],
    ) -> DatabaseAPIKeys:
        configured_key_count = await count_configured_keys(core)
        return DatabaseAPIKeys(
            DatabaseAPIKeysDependencies(
                core=core,
                config=config,
                fernet=fernet,
                configured_key_count=configured_key_count,
            )
        )

    def __init__(self, deps: DatabaseAPIKeysDependencies) -> None:
        self.core = deps.core
        self.config = deps.config
        self.cryptor = BearerTokenHashCryptor(deps.fernet)
        self._mutation_lock = asyncio.Lock()
        self._protection_tracker = OpenAIProtectionStateTracker(
            deps.configured_key_count,
        )

    @property
    def protection_state(self) -> OpenAIProtectionState:
        return self._protection_tracker.protection_state

    async def count_active_keys(self) -> int:
        return await count_active_keys_method(self)

    async def count_non_revoked_keys_without_expiration(self) -> int:
        return await count_non_revoked_keys_without_expiration_method(self)

    async def has_any_active_key(self) -> bool:
        return await has_any_active_key_method(self)

    async def list_keys(self, include_revoked: bool = False) -> list[JSONDict]:
        return await list_keys_method(self, include_revoked)

    async def insert_key(self, request: InsertAPIKeyRequest) -> JSONDict:
        async with self._mutation_lock:
            snapshot = self._protection_tracker.enter_insert_submission()
            try:
                record, remaining_count = await insert_key_method(self, request)
            except asyncio.CancelledError:
                self._protection_tracker.retain_uncertain_insert(
                    snapshot,
                    committed=None,
                )
                raise
            except DatabaseTimeoutError as exception:
                if exception.operation_status == "committed":
                    self._protection_tracker.retain_uncertain_insert(
                        snapshot,
                        committed=True,
                    )
                elif exception.operation_status in {
                    "failed",
                    "not_committed",
                    "skipped",
                }:
                    self._protection_tracker.restore(snapshot)
                else:
                    self._protection_tracker.retain_uncertain_insert(
                        snapshot,
                        committed=None,
                    )
                raise
            except HANDLED_RUNTIME_EXCEPTIONS:
                self._protection_tracker.restore(snapshot)
                raise
            self._protection_tracker.apply_committed_count(remaining_count)
            return record

    async def get_key_by_id(self, key_id: str) -> JSONDict | None:
        return await get_key_by_id_method(self, key_id)

    async def get_key_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
    ) -> JSONDict | None:
        return await get_key_by_fingerprints_method(self, fingerprints)

    async def get_active_key_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
    ) -> JSONDict | None:
        return await get_active_key_by_fingerprints_method(self, fingerprints)

    async def record_usage(
        self,
        key_id: str,
        client_ip: str | None,
        timestamp: int | None = None,
    ) -> None:
        await record_usage_method(self, key_id, client_ip, timestamp)

    async def revoke_key(self, key_id: str, revoked_by: int | None) -> JSONDict | None:
        return await revoke_key_method(self, key_id, revoked_by)

    async def delete_key(self, key_id: str) -> int:
        return await self._apply_deletion(
            partial(delete_key_method, self, key_id),
            maximum_deleted_records=1,
        )

    async def delete_all_keys(self) -> int:
        return await self._apply_deletion(
            partial(delete_all_keys_method, self),
            maximum_deleted_records=None,
        )

    async def _apply_deletion(
        self,
        operation: Callable[[], Awaitable[tuple[int, int]]],
        *,
        maximum_deleted_records: int | None,
    ) -> int:
        async with self._mutation_lock:
            snapshot = self._protection_tracker.enter_deletion_submission(
                maximum_deleted_records=maximum_deleted_records,
            )
            try:
                deleted_count, remaining_count = await operation()
            except DatabaseTimeoutError as exception:
                if exception.operation_status in {
                    "failed",
                    "not_committed",
                    "skipped",
                }:
                    self._protection_tracker.restore(snapshot)
                raise
            except HANDLED_RUNTIME_EXCEPTIONS:
                self._protection_tracker.restore(snapshot)
                raise
            self._protection_tracker.apply_committed_count(remaining_count)
            return deleted_count

    async def get_quota_config(self, key_id: str) -> JSONDict:
        return await get_quota_config_method(self, key_id)

    async def set_quota_config(
        self,
        key_id: str,
        payload: JSONDict,
        *,
        reset_usage: bool = True,
    ) -> JSONDict:
        return await set_quota_config_method(
            self,
            key_id,
            payload,
            reset_usage=reset_usage,
        )

    async def get_active_key_id_for_user(self, user_id: int) -> str | None:
        return await get_active_key_id_for_user_method(self, user_id)

    async def assign_user_to_key(
        self,
        key_id: str,
        user_id: int,
    ) -> APIKeyAssignmentOutcome:
        return await assign_user_to_key_method(self, key_id, user_id)

    async def unassign_user_from_key(self, key_id: str) -> bool:
        return await unassign_user_from_key_method(self, key_id)

    async def get_quota_status(self, key_id: str, now_ts: int) -> JSONDict:
        return await get_quota_status_method(self, key_id, now_ts)

    async def reserve_quota_units_for_mode(
        self,
        key_id: str,
        expected_mode: str,
        estimate_units: int,
        now_ts: int,
        client_ip: str | None = None,
        *,
        record_usage: bool = False,
    ) -> JSONDict:
        return await reserve_quota_units_for_mode_method(
            self,
            key_id,
            expected_mode,
            estimate_units,
            now_ts,
            client_ip,
            record_usage=record_usage,
        )

    async def reconcile_quota_reservations(
        self,
        now_ts: int,
        *,
        batch_limit: int = 200,
    ) -> JSONDict:
        return await reconcile_quota_reservations_method(
            self,
            now_ts,
            batch_limit=batch_limit,
        )

    async def finalize_quota_reservation(
        self,
        key_id: str,
        reservation: JSONDict,
        actual_units: int,
        now_ts: int,
    ) -> None:
        await finalize_quota_reservation_method(
            self,
            key_id,
            reservation,
            actual_units,
            now_ts,
        )
