"""SoAI - Agent turn-state writer [backend/core/agent/turn_state_writer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.agent.prompt_replay import AgentInferencePromptReplay
from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.turn_record_fields import read_turn_int, read_turn_state_header
from core.agent.turn_state_requests import build_turn_state_request
from core.agent.turn_write_conflicts import (
    AgentTurnAlreadyFinalizedDuringWriteError,
    AgentTurnFinalizedWriteConflictError,
)
from core.concurrency.cancellation_cleanup import run_idempotent_current_task_operation
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.tool_calls.activity_snapshot_merging import upsert_tool_activity_snapshot
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from core.conversations.input_claim import ConversationInputClaim
    from core.events.types_conversation import (
        ToolCallCompletedEvent,
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )
    from core.skills.checkpoint import SkillActivationCheckpoint

__all__ = ("TurnStateWriter",)


@dataclass(slots=True)
class TurnStateWriter:
    database_agent_turns: DatabaseAgentTurnsProtocol
    resolve_turn_state_sequence: Callable[[], int]
    seed_record: JSONDict
    execution_token: str
    mode: str
    max_iterations: int
    turn_cancellation_id: str
    todo_state: AgentTurnTodoState
    started_at_ms: int
    latest_iteration_index: int
    latest_status: str
    latest_active_inference_cancellation_id: str | None
    latest_reached_max_iterations: bool
    latest_error_message: str | None
    latest_error_type: str | None
    latest_reasoning_text: str = ""
    latest_assistant_text: str | None = None
    latest_tool_calls: list[JSONDict] = field(default_factory=list[JSONDict])
    latest_tool_results: list[JSONValue] = field(default_factory=list[JSONValue])
    latest_activities: list[JSONDict] = field(default_factory=list[JSONDict])
    latest_token_usage: JSONDict | None = None
    latest_skill_activation: SkillActivationCheckpoint | None = None
    skill_input_claim: ConversationInputClaim | None = None
    _write_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.execution_token.strip():
            raise ValidationError("Agent turn execution_token is required.")

    def update_todo_state(
        self,
        *,
        todo: list[JSONDict],
        explanation: str | None,
        revision: int,
        updated_at_ms: int | None,
    ) -> None:
        self.todo_state.todo = [dict(entry) for entry in todo]
        self.todo_state.todo_explanation = explanation
        self.todo_state.todo_revision = int(revision)
        self.todo_state.todo_updated_at_ms = (
            int(updated_at_ms) if updated_at_ms is not None and updated_at_ms >= 0 else None
        )

    def resolve_pending_inference_cancellation_id(self, *, iteration_index: int) -> str | None:
        cancellation_id = self.latest_active_inference_cancellation_id
        if cancellation_id is None:
            return None
        if self.latest_status != AGENT_TURN_STATUS_RUNNING:
            return None
        if self.latest_iteration_index != int(iteration_index):
            return None
        if self.latest_assistant_text is not None:
            return None
        if self.latest_tool_calls:
            return None
        if self.latest_tool_results:
            return None
        return cancellation_id

    async def persist_tool_activity(
        self,
        *,
        event: ToolCallCreatedEvent | ToolCallStartedEvent | ToolCallCompletedEvent,
        activity_sequence: int,
        text_length_before: int,
    ) -> None:
        async with self._write_lock:
            self.latest_activities = upsert_tool_activity_snapshot(
                self.latest_activities,
                event=event,
                activity_sequence=activity_sequence,
                text_length_before=text_length_before,
            )
            await self._write_current_state()

    def _reset_running_state(
        self,
        *,
        iteration_index: int,
        active_inference_cancellation_id: str | None,
    ) -> None:
        self.latest_iteration_index = int(iteration_index)
        self.latest_status = AGENT_TURN_STATUS_RUNNING
        self.latest_active_inference_cancellation_id = active_inference_cancellation_id
        self.latest_reached_max_iterations = False
        self.latest_error_message = None
        self.latest_error_type = None

    async def inference_started(self, *, iteration_index: int, cancellation_id: str) -> None:
        async with self._write_lock:
            self.latest_assistant_text = None
            self.latest_reasoning_text = ""
            self.latest_tool_calls = []
            self.latest_tool_results = []
            self._reset_running_state(
                iteration_index=iteration_index,
                active_inference_cancellation_id=cancellation_id,
            )
            await self._write_current_state()

    async def after_inference(
        self,
        iteration_index: int,
        assistant_text: str | None,
        tool_calls: list[JSONDict],
        *,
        reasoning_text: str = "",
        prompt_replay: AgentInferencePromptReplay | None = None,
    ) -> None:
        async with self._write_lock:
            self.latest_assistant_text = assistant_text
            self.latest_reasoning_text = reasoning_text if tool_calls else ""
            self.latest_tool_calls = [dict(entry) for entry in tool_calls]
            self.latest_tool_results = []
            self._reset_running_state(
                iteration_index=iteration_index,
                active_inference_cancellation_id=None,
            )
            await self._write_current_state(prompt_replay=prompt_replay)

    async def after_tools(
        self,
        *,
        iteration_index: int,
        assistant_text: str | None,
        tool_calls: list[JSONDict],
        tool_results: list[JSONValue],
        prompt_replay: AgentInferencePromptReplay | None = None,
    ) -> None:
        async with self._write_lock:
            self.latest_assistant_text = assistant_text
            self.latest_tool_calls = [dict(entry) for entry in tool_calls]
            self.latest_tool_results = list(tool_results)
            self._reset_running_state(
                iteration_index=iteration_index,
                active_inference_cancellation_id=None,
            )
            await self._write_current_state(prompt_replay=prompt_replay)

    async def checkpoint_skill_activation(
        self,
        *,
        iteration_index: int,
        call_id: str,
        result: JSONDict,
        skill_activation: SkillActivationCheckpoint,
    ) -> None:
        async with self._write_lock:
            position = len(self.latest_tool_results)
            if (
                self.latest_status != AGENT_TURN_STATUS_RUNNING
                or self.latest_iteration_index != iteration_index
                or position >= len(self.latest_tool_calls)
                or self.latest_tool_calls[position].get("id") != call_id
                or self.latest_tool_calls[position].get("name") != "skill_read"
            ):
                raise ValidationError(
                    "Skill activation checkpoint does not match the active tool call."
                )
            proposed_results = [*self.latest_tool_results, result]
            write_task = create_ephemeral_task(
                self._write_current_state(
                    skill_activation=skill_activation,
                    tool_results=proposed_results,
                    skill_activation_call_id=call_id,
                ),
                name="skill-activation-checkpoint",
            )
            await run_idempotent_current_task_operation(lambda: asyncio.shield(write_task))
            self.latest_skill_activation = skill_activation
            self.latest_tool_results = proposed_results

    async def finalize_terminal(
        self,
        *,
        iteration_index: int,
        status: str,
        assistant_text: str | None,
        reached_max_iterations: bool,
        error_message: str | None,
        error_type: str | None,
        token_usage: JSONDict | None = None,
    ) -> None:
        async with self._write_lock:
            if assistant_text is not None:
                self.latest_assistant_text = assistant_text
            self.latest_token_usage = dict(token_usage) if token_usage is not None else None
            self.latest_iteration_index = int(iteration_index)
            self.latest_status = status
            self.latest_active_inference_cancellation_id = None
            self.latest_reached_max_iterations = bool(reached_max_iterations)
            self.latest_error_message = error_message
            self.latest_error_type = error_type
            await self._write_current_state()

    async def _write_current_state(
        self,
        *,
        prompt_replay: AgentInferencePromptReplay | None = None,
        skill_activation: SkillActivationCheckpoint | None = None,
        tool_results: list[JSONValue] | None = None,
        skill_activation_call_id: str | None = None,
    ) -> None:
        turn_state_sequence = int(self.resolve_turn_state_sequence())
        now = epoch_ms()
        try:
            await self.database_agent_turns.write_turn_state(
                build_turn_state_request(
                    conv_id=str(self.seed_record.get("conv_id") or ""),
                    user_id=read_turn_int(self.seed_record, "user_id") or 0,
                    turn_id=str(self.seed_record.get("turn_id") or ""),
                    header=read_turn_state_header(self.seed_record),
                    execution_token=self.execution_token,
                    status=self.latest_status,
                    mode=self.mode,
                    max_iterations=self.max_iterations,
                    iteration_index=int(self.latest_iteration_index),
                    sequence=max(0, turn_state_sequence),
                    turn_cancellation_id=self.turn_cancellation_id,
                    active_inference_cancellation_id=self.latest_active_inference_cancellation_id,
                    assistant_text=self.latest_assistant_text,
                    tool_calls=self.latest_tool_calls,
                    tool_results=(
                        tool_results if tool_results is not None else self.latest_tool_results
                    ),
                    activities=self.latest_activities,
                    reached_max_iterations=bool(self.latest_reached_max_iterations),
                    error_message=self.latest_error_message,
                    error_type=self.latest_error_type,
                    token_usage=self.latest_token_usage,
                    prompt_replay=prompt_replay,
                    skill_activation=(
                        skill_activation
                        if skill_activation is not None
                        else self.latest_skill_activation
                    ),
                    skill_input_claim=self.skill_input_claim,
                    skill_activation_call_id=skill_activation_call_id,
                    todo_state=self.todo_state,
                    started_at_ms=self.started_at_ms,
                    updated_at_ms=now,
                    finished_at_ms=(
                        now if self.latest_status != AGENT_TURN_STATUS_RUNNING else None
                    ),
                ),
            )
        except AgentTurnFinalizedWriteConflictError as exception:
            raise AgentTurnAlreadyFinalizedDuringWriteError(str(exception)) from exception
