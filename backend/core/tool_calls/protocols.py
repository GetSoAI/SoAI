"""SoAI - Core tool-call execution contracts [backend/core/tool_calls/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.database.requests import (
    CreateToolCallRequest,
    CreateToolCallResult,
    RecordToolCallLiveEventRequest,
)
from core.logging.protocols import LoggerProtocol
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DatabaseToolCallsProtocol",
    "ToolCallExecutorProtocol",
    "ToolCallProcessingProtocol",
)


@runtime_checkable
class ToolCallExecutorProtocol(Protocol):
    async def execute_openai_tool_call(
        self,
        tool_name: str,
        arguments: JSONDict,
        *,
        request_context: RequestContext,
        user_id: int,
        conv_id: str,
        call_id: str,
        storage_call_id: str,
        message_index: int,
        assistant_at_ms: int,
        assistant_turn_at_ms: int,
        model_variant_index: int,
        sequence_index: int,
        content_index_before: int,
        thinking_index_before: int,
    ) -> JSONValue: ...

    def track_background_task(self, task: asyncio.Task[None]) -> None: ...


class ToolCallProcessingProtocol(Protocol):
    async def execute_tool_calls_with_events(
        self,
        *,
        request_context: RequestContext,
        tool_context: MCPToolContext,
        raw_tool_calls: list[JSONDict],
        logger: LoggerProtocol,
        deadline_monotonic: float | None = None,
    ) -> list[JSONValue]: ...

    def schedule_tool_call_processing(
        self,
        *,
        request_context: RequestContext,
        raw_tool_calls: list[JSONDict],
        logger: LoggerProtocol,
        track_background_task: Callable[[asyncio.Task[None]], None] | None = None,
    ) -> None: ...


class DatabaseToolCallsProtocol(Protocol):
    async def create_tool_call(self, request: CreateToolCallRequest) -> CreateToolCallResult: ...

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
    ) -> JSONDict | None: ...

    async def record_tool_call_live_event(
        self,
        request: RecordToolCallLiveEventRequest,
    ) -> JSONDict: ...

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
    ) -> JSONDict | None: ...

    async def finalize_tool_call_if_unfinished(
        self,
        storage_call_id: str,
        *,
        status: str,
        error_message: str | None,
        completed_at_ms: int,
    ) -> JSONDict | None: ...

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
    ) -> JSONDict | None: ...

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
    ) -> JSONDict | None: ...

    async def get_tool_call_by_storage_id(self, storage_call_id: str) -> JSONDict | None: ...

    async def get_tool_call_for_agent_lineage(
        self,
        *,
        conv_id: str,
        call_id: str,
        turn_id: str,
        iteration_index: int,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> JSONDict | None: ...

    async def get_tool_call_for_assistant_variant(
        self,
        *,
        conv_id: str,
        call_id: str,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> JSONDict | None: ...

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
    ) -> JSONDict | None: ...

    async def get_tool_calls_for_assistant_turn(
        self,
        conv_id: str,
        assistant_turn_at_ms: int,
        model_variant_index: int,
    ) -> list[JSONDict]: ...

    async def get_tool_calls_for_turn(self, conv_id: str, turn_id: str) -> list[JSONDict]: ...
