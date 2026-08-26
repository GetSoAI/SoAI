"""SoAI - Subagent coordinator service [backend/features/agent/subagents/coordinator/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.protocols import SubagentCancelResult, SubagentSpawnRequest
from core.agent.status_values import SUBAGENT_STATUS_RUNNING
from core.di.validation import require_dependencies
from core.execution.owned_execution_tasks import (
    request_owned_execution_cancellation,
    wait_for_owned_execution_snapshot,
)
from core.execution.protocols import SubagentSnapshot
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.enums import TaskStatus
from core.tool_calls.current_tool_call import CurrentToolCallIdentity
from features.agent.subagents.coordinator.cancellation import (
    cancel_subagent_active_inference_scope_noncritical,
)
from features.agent.subagents.coordinator.spawn import spawn_subagent_execution
from features.agent.subagents.internal_protocols import (
    SubagentBackgroundExecutorProtocol,
)
from features.agent.subagents.parent_state import require_parent_subagent_state
from features.agent.subagents.reads import read_subagent_snapshot

if TYPE_CHECKING:
    from core.agent.protocols import SubagentAcceptedExecution
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "AgentSubagentService",
    "AgentSubagentServiceDependencies",
)

LOGGER_NAME = "SoAI.features.agent.coordinator_service"
OPERATION_CANCEL_SUBAGENT_ACTIVE_INFERENCE_SCOPE = (
    "agent.subagents.service.cancel_subagent.active_inference_cancel"
)


@dataclass(frozen=True, slots=True)
class AgentSubagentServiceDependencies:
    api_dependencies: ApiDependencies
    active_request_context: contextvars.ContextVar[RequestContext | None]
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None]
    background_executor: SubagentBackgroundExecutorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AgentSubagentServiceDependencies",
            api_dependencies=self.api_dependencies,
            active_request_context=self.active_request_context,
            active_tool_call_context=self.active_tool_call_context,
            background_executor=self.background_executor,
        )


class AgentSubagentService:
    def __init__(self, deps: AgentSubagentServiceDependencies) -> None:
        self._api = deps.api_dependencies
        self._active_request_context = deps.active_request_context
        self._active_tool_call_context = deps.active_tool_call_context
        self._background_executor = deps.background_executor
        self._logger = get_logger(LOGGER_NAME)

    async def spawn_subagent(
        self,
        request: SubagentSpawnRequest,
    ) -> SubagentAcceptedExecution:
        return await spawn_subagent_execution(
            api_dependencies=self._api,
            logger=self._logger,
            background_executor=self._background_executor,
            active_request_context=self._active_request_context,
            active_tool_call_context=self._active_tool_call_context,
            task=request.task,
            context=request.context,
            mode=request.mode,
            display_name=request.display_name,
            model=request.model,
            workspace_path=request.workspace_path,
            max_iterations=request.max_iterations,
            tools=request.tools,
        )

    async def get_subagent(self, *, subagent_id: str) -> SubagentSnapshot | None:
        parent_context, _tool_call_identity, parent_tool_context = require_parent_subagent_state(
            self._active_request_context,
            self._active_tool_call_context,
        )
        snapshot = await read_subagent_snapshot(
            database_agent_turns=self._api.database_agent_turns,
            task_registry_queries=self._api.task_registry_queries,
            token_collection=self._api.token_collection,
            conv_id=parent_tool_context.conv_id,
            user_id=parent_tool_context.user_id,
            subagent_id=subagent_id,
            parent_turn_id=parent_context.agent_turn_id,
        )
        if snapshot is None:
            self._logger.debug(
                "Subagent snapshot not found or out of scope: conv_id=%s user_id=%s parent_turn_id=%s subagent_id=%s",
                parent_tool_context.conv_id,
                parent_tool_context.user_id,
                parent_context.agent_turn_id,
                subagent_id,
            )
        return snapshot

    async def wait_for_subagent(
        self,
        *,
        subagent_id: str,
        timeout_ms: int | None,
    ) -> SubagentSnapshot | None:
        snapshot = await self.get_subagent(subagent_id=subagent_id)
        return await wait_for_owned_execution_snapshot(
            self._api.task_registry,
            snapshot=snapshot,
            timeout_ms=timeout_ms,
            can_wait=lambda current_snapshot: current_snapshot.status == SUBAGENT_STATUS_RUNNING,
            reload_snapshot=lambda: self.get_subagent(subagent_id=subagent_id),
        )

    async def cancel_subagent(self, *, subagent_id: str) -> SubagentCancelResult:
        parent_context, _tool_call_identity, parent_tool_context = require_parent_subagent_state(
            self._active_request_context,
            self._active_tool_call_context,
        )
        snapshot = await read_subagent_snapshot(
            database_agent_turns=self._api.database_agent_turns,
            task_registry_queries=self._api.task_registry_queries,
            token_collection=self._api.token_collection,
            conv_id=parent_tool_context.conv_id,
            user_id=parent_tool_context.user_id,
            subagent_id=subagent_id,
            parent_turn_id=parent_context.agent_turn_id,
        )
        owner_task_id = None if snapshot is None else snapshot.owner_task_id
        if (
            snapshot is None
            or snapshot.status != SUBAGENT_STATUS_RUNNING
            or owner_task_id is None
            or not owner_task_id.strip()
        ):
            return SubagentCancelResult(cancelled=False)
        task = await self._api.task_registry.get(owner_task_id)
        if task is None:
            return SubagentCancelResult(cancelled=False)
        if task.status == TaskStatus.CANCELLED or task.cancellation_requested_at_ms is not None:
            await cancel_subagent_active_inference_scope_noncritical(
                api_dependencies=self._api,
                logger=self._logger,
                trace_id=parent_context.trace_id,
                conv_id=parent_tool_context.conv_id,
                user_id=parent_tool_context.user_id,
                subagent_id=subagent_id,
                reason="Cancelled by parent agent.",
                operation=OPERATION_CANCEL_SUBAGENT_ACTIVE_INFERENCE_SCOPE,
                log_message="Failed to cancel subagent active inference scope (non-critical).",
            )
            return SubagentCancelResult(cancelled=True)
        if task.status.is_terminal():
            return SubagentCancelResult(cancelled=False)
        cancelled_task = await request_owned_execution_cancellation(
            self._api.task_registry,
            owner_task_id=owner_task_id,
            reason="Cancelled by parent agent.",
        )
        cancelled = cancelled_task is not None
        if cancelled:
            await cancel_subagent_active_inference_scope_noncritical(
                api_dependencies=self._api,
                logger=self._logger,
                trace_id=parent_context.trace_id,
                conv_id=parent_tool_context.conv_id,
                user_id=parent_tool_context.user_id,
                subagent_id=subagent_id,
                reason="Cancelled by parent agent.",
                operation=OPERATION_CANCEL_SUBAGENT_ACTIVE_INFERENCE_SCOPE,
                log_message="Failed to cancel subagent active inference scope (non-critical).",
            )
        return SubagentCancelResult(cancelled=cancelled)
