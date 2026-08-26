"""SoAI - WebUI database MCP access token protocol [backend/core/auth/protocols_database_mcp_access_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.database.requests import InsertMcpAccessTokenRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabaseMcpAccessTokensProtocol",)


class DatabaseMcpAccessTokensProtocol(Protocol):
    async def count_non_revoked_tokens_without_expiration(self) -> int: ...

    async def list_tokens_for_user(
        self,
        user_id: int,
        *,
        include_revoked: bool = False,
    ) -> list[JSONDict]: ...

    async def insert_token(self, request: InsertMcpAccessTokenRequest) -> JSONDict: ...

    async def get_token_by_id(self, token_id: str) -> JSONDict | None: ...

    async def get_token_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
    ) -> JSONDict | None: ...

    async def get_active_token_by_fingerprints(
        self,
        fingerprints: tuple[str, ...],
        *,
        now_ms: int,
    ) -> JSONDict | None: ...

    async def record_last_used(self, token_id: str, *, now_ms: int) -> None: ...

    async def revoke_token(
        self,
        token_id: str,
        *,
        revoked_by: int | None,
        now_ms: int,
    ) -> JSONDict | None: ...
