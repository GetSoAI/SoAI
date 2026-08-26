"""SoAI - WebUI database prompt protocol definitions [backend/core/prompts/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabasePromptsProtocol",)


class DatabasePromptsProtocol(Protocol):
    async def create_prompt(
        self,
        user_id: int,
        name: str,
        content: str,
        color: str | None = None,
    ) -> JSONDict: ...
    async def get_prompt(self, prompt_id: str, user_id: int) -> JSONDict | None: ...
    async def list_prompts(self, user_id: int, color: str | None = None) -> list[JSONDict]: ...
    async def search_prompt_titles(
        self,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[JSONDict]: ...
    async def update_prompt(
        self,
        prompt_id: str,
        user_id: int,
        name: str,
        content: str,
        color: str | None = None,
    ) -> JSONDict | None: ...
    async def delete_prompt(self, prompt_id: str, user_id: int) -> bool: ...
    async def delete_prompts_batch(self, prompt_ids: list[str], user_id: int) -> int: ...
