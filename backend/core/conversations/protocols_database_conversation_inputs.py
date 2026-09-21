"""SoAI - Conversation input database protocols [backend/core/conversations/protocols_database_conversation_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.conversations.conversation_input_active_state import (
        ActiveConversationInputSummary,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = ("DatabaseConversationInputsProtocol",)


class DatabaseConversationInputsProtocol(Protocol):
    async def enqueue_input(
        self,
        *,
        conv_id: str,
        user_id: int,
        input_type: str,
        transport_origin: str,
        text: str | None,
        prompt_history_text: str | None,
        attachment_content: list[JSONValue],
        model_settings: JSONDict | None,
        expected_input_generation: int,
        client_id: str | None = None,
        client_request_id: str | None = None,
        messaging_ingress_id: str | None = None,
        source_metadata: JSONDict | None = None,
        media_descriptors: list[JSONDict] | None = None,
    ) -> JSONDict: ...

    async def list_active_inputs(
        self,
        *,
        conv_id: str,
        user_id: int,
    ) -> list[JSONDict]: ...

    async def summarize_active_inputs(
        self,
        *,
        conv_id: str,
        user_id: int,
    ) -> ActiveConversationInputSummary: ...

    async def has_pending_input_type(
        self,
        *,
        conv_id: str,
        user_id: int,
        input_type: str,
    ) -> bool: ...

    async def list_running_chat_inputs_for_client(
        self,
        *,
        user_id: int,
        client_id: str,
    ) -> list[JSONDict]: ...

    async def cancel_input(
        self,
        *,
        conv_id: str,
        user_id: int,
        input_id: str,
    ) -> JSONDict: ...

    async def force_pending_steers(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str | None = None,
        agent_turn_id: str | None = None,
    ) -> JSONDict: ...
