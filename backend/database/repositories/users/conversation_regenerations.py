"""SoAI - Durable conversation regeneration repository [backend/database/repositories/users/conversation_regenerations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.users.conversation_input_regeneration import (
    sync_admit_conversation_regeneration,
)
from database.repositories.users.conversation_input_regeneration_admission import (
    normalize_conversation_regeneration_admission,
)
from database.repositories.users.conversation_input_regeneration_queries import (
    query_conversation_regeneration_attempt,
)
from database.repositories.users.storage_backed_repository_runtime import (
    queue_storage_backed_write,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationRegenerations",)


class DatabaseConversationRegenerations:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

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
    ) -> JSONDict:
        admission = normalize_conversation_regeneration_admission(
            conv_id=conv_id,
            client_id=client_id,
            client_request_id=client_request_id,
            regeneration_request=regeneration_request,
            model_settings=model_settings,
            settings_authority=settings_authority,
        )
        return await queue_storage_backed_write(
            self.core,
            sync_admit_conversation_regeneration,
            conv_id,
            user_id,
            admission.source_key,
            admission.client_id,
            admission.client_request_id,
            admission.regeneration_request_json,
            admission.model_settings_json,
            admission.settings_authority_json,
            admission.input_id,
            admission.request_id,
            admission.accepted_at_ms,
        )

    async def get_attempt(
        self,
        *,
        conv_id: str,
        user_id: int,
        client_id: str | None = None,
        client_request_id: str | None = None,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            query_conversation_regeneration_attempt,
            conv_id,
            user_id,
            client_id,
            client_request_id,
        )
