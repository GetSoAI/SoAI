"""SoAI - WebUI database API-key protocol [backend/core/auth/protocols_database_api_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.auth.api_key_assignment import APIKeyAssignmentOutcome
from core.auth.openai_protection import OpenAIProtectionState
from core.database.requests import InsertAPIKeyRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabaseAPIKeysProtocol",)


class DatabaseAPIKeysProtocol(Protocol):
    async def count_active_keys(self) -> int: ...

    async def count_non_revoked_keys_without_expiration(self) -> int: ...

    async def has_any_active_key(self) -> bool: ...

    @property
    def protection_state(self) -> OpenAIProtectionState: ...

    async def list_keys(self, include_revoked: bool = False) -> list[JSONDict]: ...

    async def insert_key(self, request: InsertAPIKeyRequest) -> JSONDict: ...

    async def get_key_by_id(self, key_id: str) -> JSONDict | None: ...

    async def get_key_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
    ) -> JSONDict | None: ...

    async def get_active_key_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
    ) -> JSONDict | None: ...

    async def record_usage(
        self,
        key_id: str,
        client_ip: str | None,
        timestamp: int | None = None,
    ) -> None: ...

    async def revoke_key(self, key_id: str, revoked_by: int | None) -> JSONDict | None: ...

    async def delete_key(self, key_id: str) -> int: ...

    async def delete_all_keys(self) -> int: ...

    async def get_quota_config(self, key_id: str) -> JSONDict: ...

    async def set_quota_config(
        self,
        key_id: str,
        payload: JSONDict,
        *,
        reset_usage: bool = True,
    ) -> JSONDict: ...

    async def get_quota_status(self, key_id: str, now_ts: int) -> JSONDict: ...

    async def reserve_quota_units_for_mode(
        self,
        key_id: str,
        expected_mode: str,
        estimate_units: int,
        now_ts: int,
        client_ip: str | None = None,
        *,
        record_usage: bool = False,
    ) -> JSONDict: ...

    async def finalize_quota_reservation(
        self,
        key_id: str,
        reservation: JSONDict,
        actual_units: int,
        now_ts: int,
    ) -> None: ...

    async def reconcile_quota_reservations(
        self,
        now_ts: int,
        *,
        batch_limit: int = 200,
    ) -> JSONDict: ...

    async def get_active_key_id_for_user(self, user_id: int) -> str | None: ...

    async def assign_user_to_key(
        self,
        key_id: str,
        user_id: int,
    ) -> APIKeyAssignmentOutcome: ...

    async def unassign_user_from_key(self, key_id: str) -> bool: ...
