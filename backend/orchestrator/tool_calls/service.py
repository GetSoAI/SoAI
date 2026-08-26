"""SoAI - MCP tool call execution service with persistence and events [backend/orchestrator/tool_calls/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, override

from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from core.openai.tool_calls import resolve_normalized_tool_calls
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tool_calls.claim_state import is_waitable_active_tool_call
from core.tool_calls.protocols import ToolCallProcessingProtocol
from core.tool_calls.status_values import (
    is_terminal_tool_call_status,
    resolve_terminal_tool_call_payload,
)
from core.tool_calls.visibility import should_persist_visible_tool_call_rows
from orchestrator.tool_calls.claimed_call_wait import wait_for_claimed_tool_call_result
from orchestrator.tool_calls.dependencies import ToolCallProcessorDependencies
from orchestrator.tool_calls.execution import execute_single_tool_call
from orchestrator.tool_calls.execution_inputs import prepare_tool_call_execution_input
from orchestrator.tool_calls.persistence import (
    ToolCallExecutionRecord,
    ToolCallPersistenceContext,
)
from orchestrator.tool_calls.sequence_policy import assign_tool_call_sequences

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("ToolCallProcessor",)


class ToolCallProcessor(ToolCallProcessingProtocol):
    def __init__(self, deps: ToolCallProcessorDependencies) -> None:
        self._deps = deps
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker

    @override
    async def execute_tool_calls_with_events(
        self,
        *,
        request_context: RequestContext,
        tool_context: MCPToolContext,
        raw_tool_calls: list[JSONDict],
        logger: LoggerProtocol,
        deadline_monotonic: float | None = None,
    ) -> list[JSONValue]:
        should_persist = should_persist_visible_tool_call_rows(request_context)
        existing_calls: list[JSONDict] = []
        if should_persist:
            assistant_turn_at_ms_value = tool_context.assistant_turn_at_ms
            model_variant_index_value = tool_context.model_variant_index
            if assistant_turn_at_ms_value is None or model_variant_index_value is None:
                raise StateError("Tool call persistence requires assistant turn identity.")
            existing_calls = await self._deps.database_tool_calls.get_tool_calls_for_assistant_turn(
                tool_context.conv_id,
                assistant_turn_at_ms_value,
                model_variant_index_value,
            )
        sequence_assignment = assign_tool_call_sequences(
            raw_tool_calls=raw_tool_calls,
            existing_calls=existing_calls,
        )
        normalized_calls = sequence_assignment.calls
        if not normalized_calls:
            return []
        if not should_persist:
            non_persisted_results: list[JSONValue] = []
            for tool_call in normalized_calls:
                non_persisted_results.append(
                    await execute_single_tool_call(
                        self._deps,
                        request_context=request_context,
                        tool_context=tool_context,
                        tool_call=tool_call,
                        logger=logger,
                        deadline_monotonic=deadline_monotonic,
                    ),
                )
            return non_persisted_results
        persistence_context = ToolCallPersistenceContext(
            database_tool_calls=self._deps.database_tool_calls,
            event_bus=self._deps.event_bus,
            logger=logger,
            request_context=request_context,
            tool_context=tool_context,
            persist_visible_rows=should_persist,
            publish_events=self._deps.event_bus is not None,
        )
        results: list[JSONValue] = []
        for tool_call in normalized_calls:
            call_id_value = tool_call.get("id")
            call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
            existing_call: JSONDict | None = (
                sequence_assignment.existing_by_call_id.get(call_id) if call_id else None
            )
            if existing_call is not None:
                status_value = existing_call.get("status")
                status = status_value.strip() if isinstance(status_value, str) else ""
                if is_terminal_tool_call_status(status):
                    results.append(resolve_terminal_tool_call_payload(existing_call))
                    continue
                if is_waitable_active_tool_call(existing_call):
                    storage_call_id_value = existing_call.get("id")
                    storage_call_id = (
                        storage_call_id_value.strip()
                        if isinstance(storage_call_id_value, str)
                        else ""
                    )
                    if not storage_call_id:
                        raise StateError(
                            "Persisted active tool call is missing its storage identifier.",
                        )
                    results.append(
                        await self._wait_for_active_tool_call(
                            persistence_context=persistence_context,
                            request_context=request_context,
                            tool_context=tool_context,
                            tool_call=tool_call,
                            storage_call_id=storage_call_id,
                            logger=logger,
                            deadline_monotonic=deadline_monotonic,
                        ),
                    )
                    continue
            results.append(
                await execute_single_tool_call(
                    self._deps,
                    request_context=request_context,
                    tool_context=tool_context,
                    tool_call=tool_call,
                    logger=logger,
                    deadline_monotonic=deadline_monotonic,
                ),
            )
        return results

    async def _wait_for_active_tool_call(
        self,
        *,
        persistence_context: ToolCallPersistenceContext,
        request_context: RequestContext,
        tool_context: MCPToolContext,
        tool_call: JSONDict,
        storage_call_id: str,
        logger: LoggerProtocol,
        deadline_monotonic: float | None,
    ) -> JSONValue:
        prepared_input = prepare_tool_call_execution_input(
            request_context=request_context,
            tool_context=tool_context,
            tool_call=tool_call,
        )
        record = ToolCallExecutionRecord(
            storage_call_identifier=storage_call_id,
            call_identifier=prepared_input.call_identifier,
            tool_name=prepared_input.tool_name,
            arguments_json=prepared_input.arguments_json,
            chronology=prepared_input.chronology,
        )
        return await wait_for_claimed_tool_call_result(
            database_tool_calls=self._deps.database_tool_calls,
            persistence_context=persistence_context,
            record=record,
            tool_context=tool_context,
            storage_call_identifier=storage_call_id,
            logger=logger,
            deadline_monotonic=deadline_monotonic,
        )

    @override
    def schedule_tool_call_processing(
        self,
        *,
        request_context: RequestContext,
        raw_tool_calls: list[JSONDict],
        logger: LoggerProtocol,
        track_background_task: Callable[[asyncio.Task[None]], None] | None = None,
    ) -> None:
        tool_context = request_context.mcp_tool_context
        if tool_context is None:
            return
        normalized_calls = resolve_normalized_tool_calls(raw_tool_calls)
        if not normalized_calls:
            return
        cancellation_id_value = request_context.cancellation_id
        cancellation_id = normalize_cancellation_id(cancellation_id_value)
        if not cancellation_id:
            return

        async def _execute_and_discard() -> None:
            await self.execute_tool_calls_with_events(
                request_context=request_context,
                tool_context=tool_context,
                raw_tool_calls=normalized_calls,
                logger=logger,
                deadline_monotonic=None,
            )

        task = spawn_tracked_task(
            _execute_and_discard(),
            name=f"tool-call-processing-{uuid.uuid4().hex[:10]}",
            logger=logger,
            cancellation_binder=self._cancellation_binder,
            cancellation_id=cancellation_id,
            owner="tool_call_processing",
            finalizer_tracker=self._finalizer_tracker,
        )
        if track_background_task is not None and callable(track_background_task):
            track_background_task(task)
