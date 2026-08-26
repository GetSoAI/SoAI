"""SoAI - Durable conversation input persistence [backend/database/repositories/users/conversation_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.validation.strings import coerce_required_non_empty_str
from database.repositories.users.conversation_input_active_state_reads import (
    query_active_conversation_input_summary,
)
from database.repositories.users.conversation_input_admission import (
    normalize_conversation_input_admission,
)
from database.repositories.users.conversation_input_claim_reconciliation import (
    sync_reconcile_abandoned_conversation_input_claims,
)
from database.repositories.users.conversation_input_claims import (
    sync_claim_next_conversation_input,
)
from database.repositories.users.conversation_input_force_steering import (
    sync_force_pending_conversation_steers,
)
from database.repositories.users.conversation_input_materialization import (
    sync_materialize_claimed_conversation_input,
)
from database.repositories.users.conversation_input_media_ingestion import (
    sync_attach_ingested_input_media,
)
from database.repositories.users.conversation_input_queries import (
    has_pending_input_type,
    query_active_inputs,
    query_conversation_input_execution_settings,
    query_conversation_input_variant_outcomes,
    query_running_chat_inputs_for_client,
    require_conversation_input_claim,
)
from database.repositories.users.conversation_input_sync_cancel import (
    sync_cancel_conversation_input,
)
from database.repositories.users.conversation_input_sync_enqueue import (
    sync_enqueue_conversation_input,
)
from database.repositories.users.conversation_input_terminalization import (
    sync_terminalize_conversation_input,
)
from database.repositories.users.conversation_input_validation import (
    now_ms,
    require_client_id,
    require_input_id,
    require_input_type,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.storage_backed_repository_runtime import (
    queue_storage_backed_write,
    resolve_storage_backed_repository_root,
)

if TYPE_CHECKING:
    from core.conversations.conversation_input_active_state import ActiveConversationInputSummary
    from core.types.json import JSONDict, JSONValue
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationInputs",)


class DatabaseConversationInputs:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.files = deps.files
        self.event_bus = deps.event_bus
        self.storage_root = resolve_storage_backed_repository_root(deps)

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
    ) -> JSONDict:
        admission = normalize_conversation_input_admission(
            conv_id=conv_id,
            input_type=input_type,
            transport_origin=transport_origin,
            text=text,
            prompt_history_text=prompt_history_text,
            attachment_content=attachment_content,
            model_settings=model_settings,
            expected_input_generation=expected_input_generation,
            client_id=client_id,
            client_request_id=client_request_id,
            messaging_ingress_id=messaging_ingress_id,
            media_descriptors=media_descriptors,
        )
        return await queue_storage_backed_write(
            self.core,
            sync_enqueue_conversation_input,
            conv_id,
            user_id,
            admission.input_type,
            admission.transport_origin,
            admission.text,
            admission.prompt_history_text,
            serialize_json_compact_stable(admission.attachment_content),
            admission.model_settings_json,
            admission.source_key,
            admission.client_id,
            admission.client_request_id,
            admission.messaging_ingress_id,
            serialize_json_compact_stable(source_metadata or {}),
            serialize_json_compact_stable(admission.media_descriptors),
            admission.input_id,
            admission.accepted_at_ms,
            admission.expected_input_generation,
            self.storage_root,
        )

    async def list_active_inputs(self, *, conv_id: str, user_id: int) -> list[JSONDict]:
        return await self.core.reader.execute_read(query_active_inputs, conv_id, user_id)

    async def summarize_active_inputs(
        self,
        *,
        conv_id: str,
        user_id: int,
    ) -> ActiveConversationInputSummary:
        return await self.core.reader.execute_read(
            query_active_conversation_input_summary,
            conv_id,
            user_id,
        )

    async def has_pending_input_type(
        self,
        *,
        conv_id: str,
        user_id: int,
        input_type: str,
    ) -> bool:
        return await self.core.reader.execute_read(
            has_pending_input_type,
            conv_id,
            user_id,
            require_input_type(input_type),
        )

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

    async def list_running_chat_inputs_for_client(
        self,
        *,
        user_id: int,
        client_id: str,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            query_running_chat_inputs_for_client,
            user_id,
            require_client_id(client_id),
        )

    async def cancel_input(self, *, conv_id: str, user_id: int, input_id: str) -> JSONDict:
        cancelled = await queue_storage_backed_write(
            self.core,
            sync_cancel_conversation_input,
            conv_id,
            user_id,
            require_input_id(input_id),
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return cancelled

    async def force_pending_steers(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str | None = None,
        agent_turn_id: str | None = None,
    ) -> JSONDict:
        result = await queue_storage_backed_write(
            self.core,
            sync_force_pending_conversation_steers,
            conv_id,
            user_id,
            (
                coerce_required_non_empty_str(request_id, label="request_id")
                if request_id is not None
                else None
            ),
            (
                coerce_required_non_empty_str(agent_turn_id, label="agent_turn_id")
                if agent_turn_id is not None
                else None
            ),
        )
        if result.get("created") is True:
            notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return result

    async def claim_next_input(
        self,
        *,
        claim_owner: str,
        server_boot_id: str,
    ) -> JSONDict | None:
        return await queue_storage_backed_write(
            self.core,
            sync_claim_next_conversation_input,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            now_ms(),
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
