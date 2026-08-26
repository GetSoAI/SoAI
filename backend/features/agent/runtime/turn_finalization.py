"""SoAI - Shared agent turn finalization helpers [backend/features/agent/runtime/turn_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.task_groups import DEFAULT_CANCELLATION_TIMEOUT_SEC
from core.errors.exceptions import SoAITimeoutError
from core.execution.owned_execution_tasks import request_owned_execution_cancellation
from core.logging.trace import get_logger
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.identifiers import normalize_optional_task_id
from core.tasks.task_cancellation import request_cancellation_scope
from features.agent.runtime.non_streaming_turn_events import publish_turn_terminal_event
from features.agent.runtime.turn_engine import AgentTurnResult

if TYPE_CHECKING:
    from core.agent.turn_state_writer import TurnStateWriter
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.events.types_base import Event
    from core.openai.usage.models import CanonicalUsage
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import ActionSequenceTracker, TurnPrimitives

__all__ = (
    "build_agent_turn_result",
    "cancel_active_subagent_turns",
    "finalize_turn_state",
)

LOGGER_NAME = "SoAI.features.agent.turn_finalization"


async def _wait_for_cancelled_subagent_task(
    task_registry: TaskRegistryProtocol,
    task_id: str,
) -> str | None:
    try:
        completed_task = await task_registry.wait_for_completion(
            task_id,
            timeout=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
    except SoAITimeoutError:
        return task_id
    if completed_task is not None and not completed_task.status.is_terminal():
        return task_id
    return None


async def finalize_turn_state(
    *,
    turn_state_writer: TurnStateWriter,
    emit_event: Callable[[Event], Awaitable[None]],
    sequence_tracker: ActionSequenceTracker,
    primitives: TurnPrimitives,
    iteration_index: int,
    final_status: str,
    final_text: str | None,
    reached_max_iterations: bool,
    final_error_message: str | None,
    final_error_type: str | None,
    token_usage: JSONDict | None,
) -> None:
    await turn_state_writer.finalize_terminal(
        iteration_index=iteration_index,
        status=final_status,
        assistant_text=final_text,
        reached_max_iterations=reached_max_iterations,
        error_message=final_error_message,
        error_type=final_error_type,
        token_usage=token_usage,
    )
    await publish_turn_terminal_event(
        emit_event=emit_event,
        final_status=final_status,
        user_id=primitives.user_id,
        conv_id=primitives.conv_id,
        turn_id=primitives.turn_id,
        iteration_index=iteration_index,
        next_action_sequence=sequence_tracker.next_sequence,
        reached_max_iterations=reached_max_iterations,
        error_message=final_error_message,
        error_type=final_error_type,
    )


async def cancel_active_subagent_turns(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry: TaskRegistryProtocol | None,
    conv_id: str,
    user_id: int,
    parent_turn_id: str,
) -> None:
    if task_registry is None:
        return
    subagent_turns = await database_agent_turns.get_running_subagent_turns(
        conv_id=conv_id,
        user_id=user_id,
        parent_turn_id=parent_turn_id,
    )
    task_ids_to_wait: list[str] = []
    cancellation_ids_seen: set[str] = set()
    task_ids_seen: set[str] = set()
    for subagent_turn in subagent_turns:
        active_inference_value = subagent_turn.get("active_inference_cancellation_id")
        active_inference_cancellation_id = normalize_cancellation_id(
            active_inference_value if isinstance(active_inference_value, str) else None,
        )
        if (
            active_inference_cancellation_id
            and active_inference_cancellation_id not in cancellation_ids_seen
        ):
            cancellation_ids_seen.add(active_inference_cancellation_id)
            await request_cancellation_scope(
                task_registry,
                active_inference_cancellation_id,
                reason="Parent turn finalized.",
            )
        task_id = normalize_optional_task_id(subagent_turn.get("owner_task_id"))
        if task_id is None or task_id in task_ids_seen:
            continue
        task_ids_seen.add(task_id)
        cancelled_task = await request_owned_execution_cancellation(
            task_registry,
            owner_task_id=task_id,
            reason="Parent turn finalized.",
        )
        if cancelled_task is not None:
            task_ids_to_wait.append(task_id)
    completion_waits = [
        _wait_for_cancelled_subagent_task(task_registry, task_id) for task_id in task_ids_to_wait
    ]
    wait_results = await asyncio.gather(
        *completion_waits,
        return_exceptions=True,
    )
    pending_task_ids: list[str] = []
    for wait_result in wait_results:
        if isinstance(wait_result, BaseException):
            raise wait_result
        if wait_result is not None:
            pending_task_ids.append(wait_result)
    if pending_task_ids:
        get_logger(LOGGER_NAME).warning(
            "Parent turn %s finalized with %d subagent cancellation(s) still pending.",
            parent_turn_id,
            len(pending_task_ids),
        )


def build_agent_turn_result(
    *,
    final_payload: JSONDict,
    usage_aggregate: CanonicalUsage | None,
    reached_max_iterations: bool,
) -> AgentTurnResult:
    if usage_aggregate is not None:
        final_payload["usage"] = {
            "prompt_tokens": usage_aggregate.prompt_tokens,
            "completion_tokens": usage_aggregate.completion_tokens,
            "total_tokens": usage_aggregate.total_tokens,
            "usage_source": usage_aggregate.usage_source,
        }
    return AgentTurnResult(
        final_payload=final_payload,
        reached_max_iterations=reached_max_iterations,
    )
