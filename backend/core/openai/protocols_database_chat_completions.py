"""SoAI - OpenAI chat completions storage database protocol [backend/core/openai/protocols_database_chat_completions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.types.json import JSONDict

__all__ = ("DatabaseOpenAIChatCompletionsProtocol",)


class DatabaseOpenAIChatCompletionsProtocol(Protocol):
    async def upsert_chat_completion(
        self,
        *,
        completion_id: str,
        task_id: str,
        api_key_id: str | None,
        model: str,
        created_at_seconds: int,
        store: bool,
        request_json: JSONDict,
        completion_json: JSONDict,
        metadata_json: JSONDict,
    ) -> None: ...

    async def get_chat_completion_record(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
    ) -> JSONDict | None: ...

    async def get_cursor_for_completion(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
    ) -> tuple[int, str] | None: ...

    async def list_chat_completions(
        self,
        *,
        api_key_id: str | None,
        model: str | None,
        after: str | None,
        limit: int,
        order: str,
        metadata_filters: dict[str, str],
    ) -> tuple[tuple[JSONDict, ...], bool]: ...

    async def update_chat_completion_metadata(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
        metadata: JSONDict,
    ) -> bool: ...

    async def mark_chat_completion_deleted(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
        deleted_at_ms: int | None = None,
    ) -> bool: ...
