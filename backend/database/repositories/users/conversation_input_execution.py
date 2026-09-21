"""SoAI - Durable conversation input execution persistence [backend/database/repositories/users/conversation_input_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.strings import coerce_required_non_empty_str
from database.repositories.users.conversation_input_claim_deferral import (
    sync_defer_conversation_input_claim,
)
from database.repositories.users.conversation_input_claim_reconciliation import (
    sync_reconcile_abandoned_conversation_input_claims,
)
from database.repositories.users.conversation_input_claims import (
    sync_claim_next_conversation_input,
)
from database.repositories.users.conversation_input_materialization import (
    sync_materialize_claimed_conversation_input,
)
from database.repositories.users.conversation_input_media_ingestion import (
    sync_attach_ingested_input_media,
)
from database.repositories.users.conversation_input_queries import (
    query_conversation_input_execution_settings,
    query_conversation_input_variant_outcomes,
    require_conversation_input_claim,
)
from database.repositories.users.conversation_input_terminalization import (
    sync_terminalize_conversation_input,
)
from database.repositories.users.conversation_input_validation import (
    now_ms,
    require_input_id,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.storage_backed_repository_runtime import (
    queue_storage_backed_write,
    resolve_storage_backed_repository_root,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationInputExecution",)


class DatabaseConversationInputExecution:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.files = deps.files
        self.event_bus = deps.event_bus
        self.storage_root = resolve_storage_backed_repository_root(deps)

    async def get_input_execution_settings(self, *, input_id: str) -> JSONDict:
        return await self.core.reader.execute_read(
            query_conversation_input_execution_settings,
            require_input_id(input_id),
        )

    async def list_input_variant_outcomes(self, *, input_id: str) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            query_conversation_input_variant_outcomes,
            require_input_id(input_id),
        )

    async def claim_next_input(
        self,
        *,
        claim_owner: str,
        server_boot_id: str,
        excluded_conversation_ids: tuple[str, ...] = (),
    ) -> JSONDict | None:
        return await queue_storage_backed_write(
            self.core,
            sync_claim_next_conversation_input,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            now_ms(),
            excluded_conversation_ids,
        )

    async def defer_claim(
        self,
        *,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> bool:
        return await queue_storage_backed_write(
            self.core,
            sync_defer_conversation_input_claim,
            require_input_id(input_id),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
        )

    async def materialize_claimed_input(
        self,
        *,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> JSONDict:
        normalized_input_id = require_input_id(input_id)
        return await queue_storage_backed_write(
            self.core,
            sync_materialize_claimed_conversation_input,
            normalized_input_id,
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            f"chat_{normalized_input_id}",
            self.storage_root,
            self.files,
        )

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
    ) -> JSONDict:
        return await queue_storage_backed_write(
            self.core,
            sync_attach_ingested_input_media,
            conv_id,
            user_id,
            require_input_id(input_id),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            expected_media_descriptors,
            attachment_content,
            now_ms(),
            self.storage_root,
        )

    async def require_active_claim(
        self,
        *,
        input_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> None:
        await self.core.reader.execute_read(
            require_conversation_input_claim,
            require_input_id(input_id),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
        )

    async def reconcile_abandoned_input_claims(self) -> list[JSONDict]:
        recovered = await queue_storage_backed_write(
            self.core,
            sync_reconcile_abandoned_conversation_input_claims,
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return recovered

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
    ) -> JSONDict:
        terminal = await queue_storage_backed_write(
            self.core,
            sync_terminalize_conversation_input,
            require_input_id(input_id),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            terminal_state,
            coerce_required_non_empty_str(terminal_code, label="terminal_code"),
            terminal_args,
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return terminal
