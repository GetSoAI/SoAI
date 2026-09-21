"""SoAI - Durable Chat stream cancellation database protocol [backend/core/conversations/protocols_database_stream_cancellations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.types.json import JSONDict

__all__ = ("DatabaseConversationStreamCancellationsProtocol",)


class DatabaseConversationStreamCancellationsProtocol(Protocol):
    async def is_accepted(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
    ) -> bool: ...

    async def is_accepted_for_input(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
    ) -> bool: ...

    async def accept(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
        force_pending_steers: bool,
        allow_unpersisted_target: bool,
    ) -> JSONDict: ...

    async def has_pending(self, *, conv_id: str, user_id: int) -> bool: ...

    async def settle_local(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
    ) -> None: ...
