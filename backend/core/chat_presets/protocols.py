"""SoAI - Chat preset repository protocol [backend/core/chat_presets/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.chat_presets.contracts import (
        ChatPresetListResult,
        ChatPresetMutationResult,
        ChatPresetSections,
    )

__all__ = ("ChatPresetRepositoryProtocol",)


class ChatPresetRepositoryProtocol(Protocol):
    async def list_chat_presets(self, user_id: int) -> ChatPresetListResult: ...

    async def create_chat_preset(
        self,
        *,
        user_id: int,
        name: str,
        sections: ChatPresetSections,
    ) -> ChatPresetMutationResult: ...

    async def rename_chat_preset(
        self,
        *,
        user_id: int,
        preset_id: str,
        expected_revision: int,
        name: str,
    ) -> ChatPresetMutationResult: ...

    async def replace_chat_preset(
        self,
        *,
        user_id: int,
        preset_id: str,
        expected_revision: int,
        name: str,
        sections: ChatPresetSections,
    ) -> ChatPresetMutationResult: ...

    async def delete_chat_preset(
        self,
        *,
        user_id: int,
        preset_id: str,
        expected_revision: int,
    ) -> ChatPresetMutationResult: ...

    async def reset_chat_presets(self, user_id: int) -> int: ...
