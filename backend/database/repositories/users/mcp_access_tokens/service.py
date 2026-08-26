"""SoAI - Database repository for MCP access token management [backend/database/repositories/users/mcp_access_tokens/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.users.bearer_token_hash_crypto import BearerTokenHashCryptor
from database.repositories.users.mcp_access_tokens.service_token_methods import (
    count_non_revoked_tokens_without_expiration_method,
    get_active_token_by_fingerprints_method,
    get_token_by_fingerprints_method,
    get_token_by_id_method,
    insert_token_method,
    list_tokens_for_user_method,
    record_last_used_method,
    revoke_token_method,
)

if TYPE_CHECKING:
    from core.database.requests import InsertMcpAccessTokenRequest
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMcpAccessTokens",)


class DatabaseMcpAccessTokens:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config
        self.cryptor = BearerTokenHashCryptor(deps.fernet)

    async def count_non_revoked_tokens_without_expiration(self) -> int:
        return await count_non_revoked_tokens_without_expiration_method(self)

    async def list_tokens_for_user(
        self,
        user_id: int,
        *,
        include_revoked: bool = False,
    ) -> list[JSONDict]:
        return await list_tokens_for_user_method(
            self,
            user_id,
            include_revoked=include_revoked,
        )

    async def insert_token(self, request: InsertMcpAccessTokenRequest) -> JSONDict:
        return await insert_token_method(self, request)

    async def get_token_by_id(self, token_id: str) -> JSONDict | None:
        return await get_token_by_id_method(self, token_id)

    async def get_token_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
    ) -> JSONDict | None:
        return await get_token_by_fingerprints_method(self, fingerprints)

    async def get_active_token_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
        *,
        now_ms: int,
    ) -> JSONDict | None:
        return await get_active_token_by_fingerprints_method(
            self,
            fingerprints,
            now_ms=now_ms,
        )

    async def record_last_used(self, token_id: str, *, now_ms: int) -> None:
        await record_last_used_method(self, token_id, now_ms=now_ms)

    async def revoke_token(
        self,
        token_id: str,
        *,
        revoked_by: int | None,
        now_ms: int,
    ) -> JSONDict | None:
        return await revoke_token_method(
            self,
            token_id,
            revoked_by=revoked_by,
            now_ms=now_ms,
        )
