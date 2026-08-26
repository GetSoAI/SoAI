"""SoAI - MCP access token repository methods [backend/database/repositories/users/mcp_access_tokens/service_token_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import InsertMcpAccessTokenRequest
from database.core.flags import FEATURE_AUTH
from database.repositories.users.mcp_access_token_row_normalization import (
    sanitize_mcp_access_token_row,
)
from database.repositories.users.mcp_access_tokens.internal_protocols import (
    DatabaseMcpAccessTokensServiceProtocol,
)
from database.repositories.users.mcp_access_tokens.read_ops import (
    count_non_revoked_tokens_without_expiration,
    get_active_token_by_fingerprints,
    get_token_by_fingerprints,
    get_token_by_id,
    list_tokens_for_user,
)
from database.repositories.users.mcp_access_tokens.write_ops import (
    sync_insert_token,
    sync_record_last_used,
    sync_revoke_token,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "count_non_revoked_tokens_without_expiration_method",
    "get_active_token_by_fingerprints_method",
    "get_token_by_fingerprints_method",
    "get_token_by_id_method",
    "insert_token_method",
    "list_tokens_for_user_method",
    "record_last_used_method",
    "revoke_token_method",
)


async def count_non_revoked_tokens_without_expiration_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
) -> int:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await count_non_revoked_tokens_without_expiration(self.core)


async def list_tokens_for_user_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
    user_id: int,
    *,
    include_revoked: bool = False,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await list_tokens_for_user(
        self.core,
        int(user_id),
        include_revoked=bool(include_revoked),
        decrypt_hash=self.cryptor.decrypt_hash,
    )


async def insert_token_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
    request: InsertMcpAccessTokenRequest,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_insert_token,
        request,
        self.cryptor.encrypt_hash,
        self.cryptor.decrypt_hash,
    )
    return sanitize_mcp_access_token_row(row) or {}


async def get_token_by_id_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
    token_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_token_by_id(self.core, token_id, decrypt_hash=self.cryptor.decrypt_hash)


async def get_token_by_fingerprints_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
    fingerprints: tuple[str, ...],
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_token_by_fingerprints(
        self.core,
        fingerprints,
        decrypt_hash=self.cryptor.decrypt_hash,
    )


async def get_active_token_by_fingerprints_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
    fingerprints: tuple[str, ...],
    *,
    now_ms: int,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return await get_active_token_by_fingerprints(
        self.core,
        fingerprints,
        now_ms=int(now_ms),
        decrypt_hash=self.cryptor.decrypt_hash,
    )


async def record_last_used_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
    token_id: str,
    *,
    now_ms: int,
) -> None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    await self.core.writer.queue_write_operation(
        sync_record_last_used,
        token_id,
        int(now_ms),
    )


async def revoke_token_method(
    self: DatabaseMcpAccessTokensServiceProtocol,
    token_id: str,
    *,
    revoked_by: int | None,
    now_ms: int,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_revoke_token,
        token_id,
        revoked_by,
        int(now_ms),
        self.cryptor.decrypt_hash,
    )
    return sanitize_mcp_access_token_row(row)
