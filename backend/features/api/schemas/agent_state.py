"""SoAI - Agent WebUI state response schemas [backend/features/api/schemas/agent_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.meta.soai_v1 import SoAIV1StrictModel
from core.validation.epoch import EPOCH_MS_MIN
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "AgentCheckpointResponse",
    "AgentShellToolStopResponse",
    "AgentPlanStateResponse",
    "AgentPlanStep",
    "AgentSubagentSnapshotResponse",
    "AgentTodoStateResponse",
    "AgentTurnCancelResponse",
    "AgentTurnCancelRequest",
)


class AgentTurnCancelRequest(SoAIV1StrictModel):
    force_pending_steers: bool


class AgentPlanStep(BaseModel):
    step: str
    status: Literal["pending", "in_progress", "completed"]


class AgentTodoStateResponse(BaseModel):
    conv_id: str
    user_id: int = Field(gt=0)
    revision: int = Field(ge=0)
    updated_at_ms: int | None = Field(default=None, ge=EPOCH_MS_MIN)
    explanation: str | None
    todo: list[AgentPlanStep]


class AgentPlanStateResponse(BaseModel):
    conv_id: str
    user_id: int = Field(gt=0)
    revision: int = Field(ge=0)
    updated_at_ms: int | None = Field(default=None, ge=EPOCH_MS_MIN)
    title: str | None
    markdown: str | None


class AgentSubagentSnapshotResponse(BaseModel):
    subagent_id: str
    execution_type: str
    owner_task_id: str | None
    status: Literal[
        "running",
        "completed",
        "error",
        "cancelled",
        "max_iterations",
        "abandoned",
    ]
    status_message: str | None
    mode: Literal["plan", "execute"]
    display_name: str | None
    conv_id: str
    parent_turn_id: str
    parent_tool_call_id: str
    parent_iteration_index: int = Field(ge=0)
    started_at_ms: int = Field(ge=EPOCH_MS_MIN)
    updated_at_ms: int = Field(ge=EPOCH_MS_MIN)
    finished_at_ms: int | None = Field(default=None, ge=EPOCH_MS_MIN)
    requested_model: str | None
    result_text: str | None
    error_message: str | None
    error_type: str | None
    token_usage: dict[str, PydanticJSONValue] | None


class AgentCheckpointResponse(BaseModel):
    conv_id: str
    user_id: int = Field(gt=0)
    turn_id: str
    execution_type: str
    turn_scope: Literal["root", "subagent"]
    parent_turn_id: str | None
    parent_tool_call_id: str | None
    parent_iteration_index: int | None = Field(default=None, ge=0)
    display_name: str | None
    requested_model: str | None
    owner_task_id: str | None
    execution_token: str
    server_boot_id: str
    status: Literal[
        "running",
        "completed",
        "error",
        "cancelled",
        "max_iterations",
        "abandoned",
    ]
    status_message: str | None
    error_message: str | None
    error_type: str | None
    mode: Literal["chat", "plan", "execute"]
    max_iterations: int = Field(gt=0)
    iteration_index: int = Field(ge=0)
    sequence: int = Field(ge=0)
    turn_cancellation_id: str | None
    active_inference_cancellation_id: str | None
    assistant_text: str | None
    tool_calls: list[dict[str, PydanticJSONValue]]
    tool_results: list[PydanticJSONValue]
    activities: list[dict[str, PydanticJSONValue]]
    reached_max_iterations: bool
    token_usage: dict[str, PydanticJSONValue] | None
    todo_revision: int = Field(ge=0)
    todo_explanation: str | None
    todo: list[AgentPlanStep]
    started_at_ms: int = Field(ge=EPOCH_MS_MIN)
    updated_at_ms: int = Field(ge=EPOCH_MS_MIN)
    finished_at_ms: int | None = Field(default=None, ge=EPOCH_MS_MIN)
    subagents: list[AgentSubagentSnapshotResponse]


class AgentTurnCancelResponse(BaseModel):
    conv_id: str
    turn_id: str
    iteration_index: int = Field(ge=0)
    sequence: int = Field(ge=0)
    status: Literal["already_terminal", "cancellation_requested"]
    terminal_status: str | None = None
    cancellation_ids: list[str] | None = None
    terminated_shell_sessions: int | None = Field(default=None, ge=0)


class AgentShellToolStopResponse(BaseModel):
    conv_id: str
    tool_call_id: str
    status: Literal["already_terminal", "cancellation_requested"]
    terminal_status: Literal["completed", "cancelled", "error"] | None = None
    owner_task_id: str | None = None
