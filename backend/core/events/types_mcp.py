"""SoAI - MCP- and RAG-related events [backend/core/events/types_mcp.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_base import Event

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "KnowledgePromptStateChangedEvent",
    "MCPNotificationEvent",
    "MCPPromptsListChangedEvent",
    "MCPResourcesListChangedEvent",
    "MCPServerAddedEvent",
    "MCPServerConnectedEvent",
    "MCPServerDisconnectedEvent",
    "MCPServerRemovedEvent",
    "MCPServerStartedEvent",
    "MCPToolInvokedEvent",
    "MCPToolsListChangedEvent",
    "RAGDocumentProcessingCancelledEvent",
    "RAGDocumentProcessingCompletedEvent",
    "RAGDocumentProcessingFailedEvent",
    "RAGDocumentProcessingStartedEvent",
    "RAGSearchCompletedEvent",
)


@dataclass(slots=True)
class MCPServerStartedEvent(Event): ...


@dataclass(slots=True)
class MCPServerAddedEvent(Event):
    server_id: str
    server_name: str


@dataclass(slots=True)
class MCPServerRemovedEvent(Event):
    server_id: str


@dataclass(slots=True)
class MCPServerConnectedEvent(Event):
    server_id: str
    server_name: str
    tools_count: int
    resources_count: int


@dataclass(slots=True)
class MCPServerDisconnectedEvent(Event):
    server_id: str
    reason: str


@dataclass(slots=True)
class MCPToolInvokedEvent(Event):
    server_id: str
    tool_name: str
    success: bool
    execution_time_ms: float


@dataclass(slots=True)
class MCPNotificationEvent(Event):
    client_id: str
    notification: JSONDict


@dataclass(slots=True)
class MCPToolsListChangedEvent(Event): ...


@dataclass(slots=True)
class MCPResourcesListChangedEvent(Event): ...


@dataclass(slots=True)
class MCPPromptsListChangedEvent(Event): ...


@dataclass(slots=True)
class KnowledgePromptStateChangedEvent(Event):
    user_id: int
    conv_id: str
    knowledge_event_id: int
    reason: str
    created_at_ms: int


@dataclass(slots=True)
class RAGDocumentProcessingStartedEvent(Event):
    document_id: str
    conv_id: str
    task_id: str
    source_type: str
    file_type: str | None = None


@dataclass(slots=True)
class RAGDocumentProcessingCompletedEvent(Event):
    document_id: str
    conv_id: str
    task_id: str
    chunks_created: int
    processing_time_ms: int


@dataclass(slots=True)
class RAGDocumentProcessingFailedEvent(Event):
    document_id: str
    conv_id: str
    task_id: str
    error_message: str
    error_type: str


@dataclass(slots=True)
class RAGDocumentProcessingCancelledEvent(Event):
    document_id: str
    conv_id: str
    task_id: str
    reason: str


@dataclass(slots=True)
class RAGSearchCompletedEvent(Event):
    conv_id: str
    query_length: int
    results_count: int
    retrieval_strategy: str
    search_time_ms: int
