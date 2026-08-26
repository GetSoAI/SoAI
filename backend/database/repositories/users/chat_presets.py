"""SoAI - Chat preset repository queue and read orchestration [backend/database/repositories/users/chat_presets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.chat_presets.canonicalization import canonicalize_chat_preset_sections
from core.chat_presets.identity import (
    canonicalize_chat_preset_name,
    require_chat_preset_id,
    require_chat_preset_revision,
)
from core.users.user_id import require_strict_user_id
from database.core.flags import FEATURE_AUTH
from database.repositories.users.chat_preset_mutations import (
    sync_create_chat_preset,
    sync_delete_chat_preset,
    sync_rename_chat_preset,
    sync_replace_chat_preset,
    sync_reset_chat_presets,
)
from database.repositories.users.chat_preset_rows import list_chat_preset_rows

if TYPE_CHECKING:
    from core.chat_presets.contracts import (
        ChatPresetListResult,
        ChatPresetMutationResult,
        ChatPresetSections,
    )
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseChatPresets",)


class DatabaseChatPresets:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    def _require_user_id(self, user_id: int) -> int:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return require_strict_user_id(user_id)

    async def list_chat_presets(self, user_id: int) -> ChatPresetListResult:
        resolved_user_id = self._require_user_id(user_id)
        return await self.core.reader.execute_read(
            list_chat_preset_rows,
            user_id=resolved_user_id,
        )

    async def create_chat_preset(
        self,
        *,
        user_id: int,
        name: str,
        sections: ChatPresetSections,
    ) -> ChatPresetMutationResult:
        resolved_user_id = self._require_user_id(user_id)
        canonical_name = canonicalize_chat_preset_name(name)
        canonical_sections = canonicalize_chat_preset_sections(sections)
        return await self.core.writer.queue_write_operation(
            sync_create_chat_preset,
            resolved_user_id,
            canonical_name,
            canonical_sections,
        )

    async def rename_chat_preset(
        self,
        *,
        user_id: int,
        preset_id: str,
        expected_revision: int,
        name: str,
    ) -> ChatPresetMutationResult:
        resolved_user_id = self._require_user_id(user_id)
        return await self.core.writer.queue_write_operation(
            sync_rename_chat_preset,
            resolved_user_id,
            require_chat_preset_id(preset_id),
            require_chat_preset_revision(expected_revision),
            canonicalize_chat_preset_name(name),
        )

    async def replace_chat_preset(
        self,
        *,
        user_id: int,
        preset_id: str,
        expected_revision: int,
        name: str,
        sections: ChatPresetSections,
    ) -> ChatPresetMutationResult:
        resolved_user_id = self._require_user_id(user_id)
        return await self.core.writer.queue_write_operation(
            sync_replace_chat_preset,
            resolved_user_id,
            require_chat_preset_id(preset_id),
            require_chat_preset_revision(expected_revision),
            canonicalize_chat_preset_name(name),
            canonicalize_chat_preset_sections(sections),
        )

    async def delete_chat_preset(
        self,
        *,
        user_id: int,
        preset_id: str,
        expected_revision: int,
    ) -> ChatPresetMutationResult:
        resolved_user_id = self._require_user_id(user_id)
        return await self.core.writer.queue_write_operation(
            sync_delete_chat_preset,
            resolved_user_id,
            require_chat_preset_id(preset_id),
            require_chat_preset_revision(expected_revision),
        )

    async def reset_chat_presets(self, user_id: int) -> int:
        resolved_user_id = self._require_user_id(user_id)
        return await self.core.writer.queue_write_operation(
            sync_reset_chat_presets,
            resolved_user_id,
        )
