"""SoAI - Core database request models used by protocols and implementations [backend/core/database/requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.protocols import AgentTurnCoreFields
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ClaimAgentTurnAbandonRequest",
    "ClaimAgentTurnStateRequest",
    "CreateRAGDocumentRequest",
    "CreateToolCallRequest",
    "CreateToolCallResult",
    "InsertAPIKeyRequest",
    "InsertMcpAccessTokenRequest",
    "ManualCompactionAssistantEventRequest",
    "ManualCompactionStartCommitRequest",
    "ManualCompactionStartCommitResult",
    "ManualCompactionTerminalCommitRequest",
    "ManualCompactionTerminalCommitResult",
    "RecordToolCallLiveEventRequest",
    "UpdateRAGConfigRequest",
    "UpdateRAGConfigWithDefaultsRequest",
    "WriteAgentTurnStateRequest",
)


@dataclass(frozen=True, slots=True)
class CreateToolCallRequest:
    call_id: str
    conv_id: str
    turn_id: str | None
    iteration_index: int | None
    message_index: int | None
    assistant_turn_at_ms: int
    model_variant_index: int
    tool_name: str
    tool_arguments: str | None
    status: str
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None
    collapsed: bool
    assistant_at_ms: int | None = None
    storage_call_id: str | None = None
    owner_task_id: str | None = None
    error_message: str | None = None
    tool_result: str | None = None
    duration_ms: int | None = None
    started_at_ms: int | None = None
    created_at_ms: int | None = None
    completed_at_ms: int | None = None
    exclusive_claim: bool = False


@dataclass(frozen=True, slots=True)
class CreateToolCallResult:
    row: JSONDict
    inserted: bool
    claimed_existing: bool

    def __post_init__(self) -> None:
        if self.inserted and self.claimed_existing:
            raise ValidationError("A tool call row cannot be both inserted and claimed.")


@dataclass(frozen=True, slots=True)
class ManualCompactionAssistantEventRequest:
    sequence: int
    assistant_revision: int
    event_type: str
    tool_payload: JSONDict
    created_at_ms: int


@dataclass(frozen=True, slots=True)
class ManualCompactionStartCommitRequest:
    conv_id: str
    user_id: int
    turn_id: str
    execution_token: str
    iteration_index: int
    tool_call_id: str
    requested_started_at_ms: int
    model_id: str | None
    mode: str
    max_iterations: int
    turn_cancellation_id: str | None
    assistant_events: tuple[ManualCompactionAssistantEventRequest, ...]
    replace_assistant_at_ms: int | None
    replace_tool_call_id: str | None
    turn_claim: ClaimAgentTurnStateRequest
    manual_regeneration_request_json: str | None = None
    manual_regeneration_expected_revision: int | None = None


@dataclass(frozen=True, slots=True)
class ManualCompactionStartCommitResult:
    assistant_at_ms: int
    message_index: int
    message_count: int
    last_modified_at_ms: int
    turn_started_sequence: int
    tool_created_sequence: int
    tool_started_sequence: int


@dataclass(frozen=True, slots=True)
class ManualCompactionTerminalCommitRequest:
    conv_id: str
    user_id: int
    turn_id: str
    execution_token: str
    iteration_index: int
    tool_call_id: str
    tool_started_at_ms: int
    completed_at_ms: int
    model_id: str | None
    assistant_at_ms: int
    finish_reason: str
    terminal_status: str
    error_message: str | None
    error_type: str | None
    turn_cancellation_id: str | None
    result_payload: JSONValue
    terminal_event: ManualCompactionAssistantEventRequest
    replace_assistant_at_ms: int | None
    replace_tool_call_id: str | None


@dataclass(frozen=True, slots=True)
class ManualCompactionTerminalCommitResult:
    assistant_at_ms: int
    message_index: int
    message_count: int
    last_modified_at_ms: int
    tool_completion_sequence: int
    turn_terminal_sequence: int


@dataclass(frozen=True, slots=True)
class RecordToolCallLiveEventRequest:
    conv_id: str
    assistant_turn_at_ms: int
    model_variant_index: int
    assistant_at_ms: int
    call_id: str
    event_type: str
    payload_json: str
    status: str
    created_at_ms: int
    duration_ms: int | None = None
    started_at_ms: int | None = None
    tool_result: str | None = None
    error_message: str | None = None
    completed_at_ms: int | None = None


@dataclass(frozen=True, slots=True)
class WriteAgentTurnStateRequest(AgentTurnCoreFields):
    expected_execution_token: str | None
    mode: str
    sequence: int
    turn_cancellation_id: str | None
    active_inference_cancellation_id: str | None
    max_iterations: int
    iteration_index: int
    assistant_text: str | None
    status: str
    tool_calls_json: str
    tool_results_json: str
    activities_json: str
    reached_max_iterations: bool
    error_message: str | None
    error_type: str | None
    token_usage_json: str | None
    todo_revision: int
    todo_explanation: str | None
    todo_json: str
    started_at_ms: int
    updated_at_ms: int
    finished_at_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ClaimAgentTurnAbandonRequest:
    turn_id: str
    execution_token: str


@dataclass(frozen=True, slots=True)
class ClaimAgentTurnStateRequest:
    turn_state: WriteAgentTurnStateRequest
    stale_running_turns: tuple[ClaimAgentTurnAbandonRequest, ...] = ()


@dataclass(frozen=True, slots=True)
class InsertAPIKeyRequest:
    key_id: str
    hashed_key: str
    salt: str
    fingerprint: str
    label: str
    prefix: str
    scopes: tuple[str, ...]
    created_by: int | None
    expires_at_ms: int | None
    rotation_reminder_at_ms: int | None
    encryption_version: int
    created_at_ms: int | None = None


@dataclass(frozen=True, slots=True)
class InsertMcpAccessTokenRequest:
    token_id: str
    user_id: int
    hashed_token: str
    salt: str
    fingerprint: str
    label: str
    prefix: str
    created_at_ms: int
    expires_at_ms: int | None
    encryption_version: int


@dataclass(frozen=True, slots=True)
class CreateRAGDocumentRequest:
    doc_id: str
    conv_id: str
    user_id: int
    file_id: str | None
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    source_type: str = "upload"
    source_url: str | None = None
    chunking_strategy: str = "token_based"
    chunk_size: int = 500
    chunk_overlap: int = 100
    embedding_model: str | None = None
    metadata: dict[str, JSONValue] | None = None


@dataclass(frozen=True, slots=True)
class UpdateRAGConfigRequest:
    conv_id: str
    enabled: bool | None = None
    retrieval_strategy: str | None = None
    top_k: int | None = None
    similarity_threshold: float | None = None
    chunking_strategy: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    embedding_model: str | None = None
    config_metadata: dict[str, JSONValue] | None = None


@dataclass(frozen=True, slots=True)
class UpdateRAGConfigWithDefaultsRequest:
    update: UpdateRAGConfigRequest
    user_id: int
    expected_embedding_selector: str | None = None
    require_matching_embedding_selector: bool = False
