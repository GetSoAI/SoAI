"""SoAI - WebUI database password-vault protocol [backend/core/conversations/protocols_database_password_vault.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.web.site_scope import SiteScope

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabasePasswordVaultProtocol",)


class DatabasePasswordVaultProtocol(Protocol):
    async def list_credentials(
        self,
        user_id: int,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[JSONDict]: ...

    async def delete_all_credentials(self, user_id: int) -> int: ...

    async def delete_credential(self, user_id: int, credential_id: str) -> bool: ...

    async def get_credential_plaintext_for_url(
        self,
        user_id: int,
        credential_id: str,
        current_page_url: str,
    ) -> tuple[SiteScope, str | None, str]: ...

    async def update_last_used(
        self,
        user_id: int,
        credential_id: str,
        last_used_at_ms: int,
    ) -> None: ...
