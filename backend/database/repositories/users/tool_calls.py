"""SoAI - Database repository for tool calls [backend/database/repositories/users/tool_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import CreateToolCallRequest, RecordToolCallLiveEventRequest
from core.tool_calls.tool_call_identity import ToolCallIdentity
from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.tool_call_insert_transactions import (
    sync_create_tool_call,
)
from database.repositories.users.tool_call_live_reads import (
    get_tool_call_live_events_page,
)
from database.repositories.users.tool_call_live_transactions import (
    sync_record_tool_call_live_event,
)
from database.repositories.users.tool_call_read_operations import (
    get_tool_call_by_identity,
    get_tool_call_by_storage_id,
    get_tool_call_for_agent_lineage,
    get_tool_call_for_assistant_variant,
    get_tool_calls_for_assistant_turn,
    get_tool_calls_for_turn,
    list_active_tool_calls_by_owner_task_prefix,
    list_tool_calls_by_owner_task,
)
from database.repositories.users.tool_call_state_transactions import (
    sync_finalize_active_tool_call_with_result,
    sync_finalize_tool_call_if_unfinished,
    sync_finalize_tool_call_if_unfinished_by_identity,
    sync_update_tool_call,
)
from database.repositories.users.tool_call_subagent_parent_finalization import (
    sync_finalize_subagent_parent_tool_call_if_unfinished,
)

if TYPE_CHECKING:
    from core.database.requests import CreateToolCallResult
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseToolCalls",)


class DatabaseToolCalls:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def create_tool_call(self, request: CreateToolCallRequest) -> CreateToolCallResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_create_tool_call,
            request,
        )

    async def update_tool_call_result(
        self,
        storage_call_id: str,
        status: str | None = None,
        tool_result: str | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
        started_at_ms: int | None = None,
        completed_at_ms: int | None = None,
        owner_task_id: str | None = None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_update_tool_call,
            storage_call_id,
            status,
            tool_result,
            error_message,
            duration_ms,
            started_at_ms,
            completed_at_ms,
            owner_task_id,
        )

    async def record_tool_call_live_event(
        self,
        request: RecordToolCallLiveEventRequest,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_record_tool_call_live_event,
            request,
        )

    async def get_tool_call_live_events_page(
        self,
        *,
        conv_id: str,
        user_id: int,
        assistant_turn_at_ms: int,
        model_variant_index: int,
        call_id: str,
        before_live_sequence: int | None,
        limit: int,
    ) -> JSONDict | None:
        return await get_tool_call_live_events_page(
            self,
            conv_id=conv_id,
            user_id=user_id,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            call_id=call_id,
            before_live_sequence=before_live_sequence,
            limit=limit,
        )

    async def finalize_tool_call_if_unfinished(
        self,
        storage_call_id: str,
        *,
        status: str,
        error_message: str | None,
        completed_at_ms: int,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_finalize_tool_call_if_unfinished,
            storage_call_id,
            status,
            error_message,
            completed_at_ms,
        )

    async def finalize_tool_call_if_unfinished_by_identity(
        self,
        *,
        conv_id: str,
        call_id: str,
        turn_id: str | None,
        iteration_index: int | None,
        message_index: int | None,
        assistant_turn_at_ms: int,
        model_variant_index: int,
        status: str,
        error_message: str | None,
        completed_at_ms: int,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_finalize_tool_call_if_unfinished_by_identity,
            conv_id,
            call_id,
            turn_id,
            iteration_index,
            message_index,
            assistant_turn_at_ms,
            model_variant_index,
            status,
            error_message,
            completed_at_ms,
        )

    async def finalize_subagent_parent_tool_call_if_unfinished(
        self,
        *,
        conv_id: str,
        parent_tool_call_id: str,
        parent_turn_id: str,
        parent_iteration_index: int,
        status: str,
        error_message: str | None,
        tool_result: str | None,
        duration_ms: int,
        completed_at_ms: int,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_finalize_subagent_parent_tool_call_if_unfinished,
            conv_id,
            parent_tool_call_id,
            parent_turn_id,
            parent_iteration_index,
            status,
            error_message,
            tool_result,
            duration_ms,
            completed_at_ms,
        )

    async def get_tool_call_by_storage_id(self, storage_call_id: str) -> JSONDict | None:
        return await get_tool_call_by_storage_id(self, storage_call_id)

    async def get_tool_call_for_agent_lineage(
        self,
        *,
        conv_id: str,
        call_id: str,
        turn_id: str,
        iteration_index: int,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> JSONDict | None:
        return await get_tool_call_for_agent_lineage(
            self,
            conv_id=conv_id,
            call_id=call_id,
            turn_id=turn_id,
            iteration_index=iteration_index,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
        )

    async def get_tool_call_for_assistant_variant(
        self,
        *,
        conv_id: str,
        call_id: str,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> JSONDict | None:
        return await get_tool_call_for_assistant_variant(
            self,
            conv_id=conv_id,
            call_id=call_id,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
        )

    async def get_tool_call_by_identity(
        self,
        *,
        conv_id: str,
        call_id: str,
        turn_id: str | None,
        iteration_index: int | None,
        message_index: int | None,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> JSONDict | None:
        identity = ToolCallIdentity(
            conv_id=conv_id,
            call_id=call_id,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            turn_id=turn_id,
            iteration_index=iteration_index,
            message_index=message_index,
        )
        return await get_tool_call_by_identity(
            self,
            conv_id=identity.conv_id,
            call_id=identity.call_id,
            turn_id=identity.turn_id,
            iteration_index=identity.iteration_index,
            message_index=identity.message_index,
            assistant_turn_at_ms=identity.assistant_turn_at_ms,
            model_variant_index=identity.model_variant_index,
        )

    async def get_tool_calls_for_assistant_turn(
        self,
        conv_id: str,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> list[JSONDict]:
        return await get_tool_calls_for_assistant_turn(
            self,
            conv_id,
            assistant_turn_at_ms,
            model_variant_index,
        )

    async def get_tool_calls_for_turn(self, conv_id: str, turn_id: str) -> list[JSONDict]:
        return await get_tool_calls_for_turn(self, conv_id, turn_id)

    async def list_tool_calls_by_owner_task(
        self,
        *,
        owner_task_id: str,
        after_storage_call_id: str = "",
        limit: int = 100,
    ) -> list[JSONDict]:
        return await list_tool_calls_by_owner_task(
            self,
            owner_task_id=owner_task_id,
            after_storage_call_id=after_storage_call_id,
            limit=limit,
        )

    async def list_active_tool_calls_by_owner_task_prefix(
        self,
        *,
        owner_task_prefix: str,
        after_storage_call_id: str = "",
        limit: int = 100,
    ) -> list[JSONDict]:
        return await list_active_tool_calls_by_owner_task_prefix(
            self,
            owner_task_prefix=owner_task_prefix,
            after_storage_call_id=after_storage_call_id,
            limit=limit,
        )

    async def finalize_active_tool_call_with_result(
        self,
        storage_call_id: str,
        *,
        status: str,
        tool_result: str,
        error_message: str | None,
        duration_ms: int,
        completed_at_ms: int,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_finalize_active_tool_call_with_result,
            storage_call_id,
            status,
            tool_result,
            error_message,
            duration_ms,
            completed_at_ms,
        )
