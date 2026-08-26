"""SoAI - Prepared chat execution contracts [backend/features/api/runtime/chat_execution/contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_models_requests import InferenceRequestReceived
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest

__all__ = (
    "PreparedChatExecution",
    "PreparedChatExecutionFailure",
    "PreparedChatExecutionStorage",
    "PreparedWebSocketChatExecutionStart",
)


@dataclass(frozen=True, slots=True)
class PreparedChatExecutionStorage:
    store_chat_completion: bool
    stored_request_json: JSONDict


@dataclass(frozen=True, slots=True)
class PreparedChatExecutionFailure:
    error_code: str
    error_message: str


@dataclass(frozen=True, slots=True)
class PreparedWebSocketChatExecutionStart:
    request_context: RequestContext
    request_json: JSONDict
    effective_model_id: str
    tool_context: MCPToolContext | None
    prepared_agent_request: PreparedExecutionRequest | None
    quota_key_id: str | None
    quota_token_reservation: JSONDict | None
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None


@dataclass(frozen=True, slots=True)
class PreparedChatExecution:
    request_context: RequestContext
    request_json: JSONDict
    inference_payload: JSONDict
    request_event_class: type[InferenceRequestReceived]
    request_source: RequestSource
    effective_model_id: str | None
    required_capabilities: tuple[str, ...]
    required_modalities: tuple[str, ...]
    tool_context: MCPToolContext | None
    prepared_agent_request: PreparedExecutionRequest | None
    api_key_id: str | None
    quota_reservation: JSONDict | None
    prompt_tokens: int | None
    user_id: int
    owner_type: str
    owner_id: str
    cancellation_id: str
    is_streaming: bool
    async_accept_requested: bool
    storage: PreparedChatExecutionStorage
