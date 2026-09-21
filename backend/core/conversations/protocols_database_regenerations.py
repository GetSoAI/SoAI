"""SoAI - Conversation regeneration database protocol [backend/core/conversations/protocols_database_regenerations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabaseConversationRegenerationsProtocol",)


class DatabaseConversationRegenerationsProtocol(Protocol):
    async def admit(
        self,
        *,
        conv_id: str,
        user_id: int,
        client_id: str,
        client_request_id: str,
        regeneration_request: JSONDict,
        model_settings: JSONDict,
        settings_authority: JSONDict,
    ) -> JSONDict: ...

    async def get_attempt(
        self,
        *,
        conv_id: str,
        user_id: int,
        client_id: str | None = None,
        client_request_id: str | None = None,
    ) -> JSONDict | None: ...
