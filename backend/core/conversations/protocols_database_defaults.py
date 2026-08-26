"""SoAI - WebUI chat identity and model defaults database protocols [backend/core/conversations/protocols_database_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DatabaseChatIdentityDefaultsProtocol",
    "DatabaseChatModelDefaultsProtocol",
)


class DatabaseChatIdentityDefaultsProtocol(Protocol):
    async def get_identity_defaults(self, user_id: int) -> JSONDict | None: ...

    async def upsert_user_display_name(
        self,
        user_id: int,
        user_display_name: str | None,
    ) -> None: ...


class DatabaseChatModelDefaultsProtocol(Protocol):
    async def get_model_defaults(self, user_id: int, model_id: str) -> JSONDict | None: ...
