"""SoAI - OpenAI Responses database protocol contract [backend/core/openai/protocols_database_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabaseOpenAIResponsesProtocol",)


class DatabaseOpenAIResponsesProtocol(Protocol):
    async def upsert_response_artifacts(
        self,
        *,
        response_id: str,
        task_id: str,
        user_id: int | None,
        api_key_id: str | None,
        model: str,
        created_at_seconds: int,
        status: str,
        store: bool,
        is_background: bool,
        stream_enabled: bool,
        response_json: JSONDict,
        input_items: Sequence[JSONDict] | None,
        input_items_created_at_ms: int,
        event_payloads: Sequence[JSONDict],
        event_sequence_start: int,
        reset_events: bool,
        create_if_missing: bool,
        event_created_at_ms: int | None = None,
    ) -> bool: ...

    async def delete_response(
        self,
        *,
        response_id: str,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> bool: ...

    async def append_nonterminal_response_event(
        self,
        *,
        response_id: str,
        response_json: JSONDict,
        event_json: JSONDict,
        event_created_at_ms: int,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> int | None: ...

    async def reconcile_terminal_background_response(self, *, task_id: str) -> int: ...

    async def get_response(
        self,
        *,
        response_id: str,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> JSONDict | None: ...

    async def get_response_record(
        self,
        *,
        response_id: str,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> JSONDict | None: ...

    async def list_events_after(
        self,
        *,
        response_id: str,
        starting_after: int,
        limit: int,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> tuple[tuple[JSONDict, ...], bool]: ...

    async def list_input_items(
        self,
        *,
        response_id: str,
        limit: int,
        order: str,
        after: str | None,
        before: str | None,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> JSONDict: ...

    def encrypt_compaction_content(self, *, content: JSONDict) -> str: ...

    def decrypt_compaction_content(self, *, encrypted_content: str) -> JSONDict: ...
