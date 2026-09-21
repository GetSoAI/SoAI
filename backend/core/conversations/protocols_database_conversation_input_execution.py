"""SoAI - Conversation input execution database protocol [backend/core/conversations/protocols_database_conversation_input_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("DatabaseConversationInputExecutionProtocol",)


class DatabaseConversationInputExecutionProtocol(Protocol):
    async def get_input_execution_settings(self, *, input_id: str) -> JSONDict: ...

    async def list_input_variant_outcomes(self, *, input_id: str) -> list[JSONDict]: ...

    async def claim_next_input(
        self,
        *,
        claim_owner: str,
        server_boot_id: str,
        excluded_conversation_ids: tuple[str, ...] = (),
    ) -> JSONDict | None: ...

    async def defer_claim(
        self,
        *,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> bool: ...

    async def materialize_claimed_input(
        self,
        *,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> JSONDict: ...

    async def attach_ingested_media(
        self,
        *,
        conv_id: str,
        user_id: int,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        expected_media_descriptors: list[JSONDict],
        attachment_content: list[JSONValue],
    ) -> JSONDict: ...

    async def require_active_claim(
        self,
        *,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> None: ...

    async def reconcile_abandoned_input_claims(self) -> list[JSONDict]: ...

    async def terminalize_input(
        self,
        *,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        terminal_state: str,
        terminal_code: str,
        terminal_args: JSONDict,
    ) -> JSONDict: ...
