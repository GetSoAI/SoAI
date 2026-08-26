"""SoAI - API key repository read and insertion methods [backend/database/repositories/users/api_keys/service_key_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import InsertAPIKeyRequest
from core.timing.epoch import epoch_ms
from database.core.flags import FEATURE_AUTH
from database.repositories.users.api_key_row_normalization import sanitize_api_key_row
from database.repositories.users.api_keys.internal_protocols import (
    DatabaseAPIKeysServiceProtocol,
)
from database.repositories.users.api_keys.read_ops import (
    count_active_keys,
    count_non_revoked_keys_without_expiration,
    get_active_key_by_fingerprints,
    get_key_by_fingerprints,
    get_key_by_id,
    has_any_active_key,
    list_keys,
)
from database.repositories.users.api_keys.write_ops import sync_insert_key

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "count_active_keys_method",
    "count_non_revoked_keys_without_expiration_method",
    "get_active_key_by_fingerprints_method",
    "get_key_by_fingerprints_method",
    "get_key_by_id_method",
    "has_any_active_key_method",
    "insert_key_method",
    "list_keys_method",
)


async def count_active_keys_method(self: DatabaseAPIKeysServiceProtocol) -> int:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await count_active_keys(self.core, now_ms=epoch_ms())


async def count_non_revoked_keys_without_expiration_method(
    self: DatabaseAPIKeysServiceProtocol,
) -> int:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await count_non_revoked_keys_without_expiration(self.core)


async def has_any_active_key_method(self: DatabaseAPIKeysServiceProtocol) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await has_any_active_key(self.core, now_ms=epoch_ms())


async def list_keys_method(
    self: DatabaseAPIKeysServiceProtocol,
    include_revoked: bool = False,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await list_keys(
        self.core,
        include_revoked=bool(include_revoked),
        decrypt_hash=self.cryptor.decrypt_hash,
    )


async def insert_key_method(
    self: DatabaseAPIKeysServiceProtocol,
    request: InsertAPIKeyRequest,
) -> tuple[JSONDict, int]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row, remaining_count = await self.core.writer.queue_write_operation(
        sync_insert_key,
        request,
        epoch_ms(),
        self.cryptor.encrypt_hash,
        self.cryptor.decrypt_hash,
    )
    return (sanitize_api_key_row(row) or {}, remaining_count)


async def get_key_by_id_method(
    self: DatabaseAPIKeysServiceProtocol,
    key_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_key_by_id(
        self.core,
        key_id,
        now_ms=epoch_ms(),
        decrypt_hash=self.cryptor.decrypt_hash,
    )


async def get_key_by_fingerprints_method(
    self: DatabaseAPIKeysServiceProtocol,
    fingerprints: tuple[str, ...],
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_key_by_fingerprints(
        self.core,
        fingerprints,
        now_ms=epoch_ms(),
        decrypt_hash=self.cryptor.decrypt_hash,
    )


async def get_active_key_by_fingerprints_method(
    self: DatabaseAPIKeysServiceProtocol,
    fingerprints: tuple[str, ...],
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_active_key_by_fingerprints(
        self.core,
        fingerprints,
        now_ms=epoch_ms(),
        decrypt_hash=self.cryptor.decrypt_hash,
    )
