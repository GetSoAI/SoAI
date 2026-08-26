"""SoAI - Knowledge prompt persistence types [backend/core/rag/knowledge_prompt_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.types.json import JSONDict

__all__ = (
    "KnowledgePromptClaimResult",
    "KnowledgePromptDeliveryClaim",
    "KnowledgePromptDeliveryRecord",
    "KnowledgePromptEventRecord",
    "KnowledgePromptProjectionInputs",
)

if TYPE_CHECKING:
    type KnowledgePromptEventType = Literal[
        "documents_added",
        "documents_removed",
        "document_processing_completed",
        "document_processing_failed",
        "document_processing_cancelled",
        "knowledge_reindex_queued",
        "knowledge_reindex_completed",
        "knowledge_reindex_failed",
        "knowledge_reindex_cancelled",
    ]
else:
    KnowledgePromptEventType = str


@dataclass(frozen=True, slots=True)
class KnowledgePromptEventRecord:
    id: int
    conv_id: str
    user_id: int
    event_type: KnowledgePromptEventType
    document_names: tuple[str, ...]
    document_count: int
    details: JSONDict
    created_at_ms: int


@dataclass(frozen=True, slots=True)
class KnowledgePromptDeliveryRecord:
    conv_id: str
    user_id: int
    last_delivered_event_id: int
    last_delivered_state_signature: str | None
    active_claim_id: str | None
    active_claim_request_id: str | None
    active_claim_event_ceiling_id: int | None
    active_claim_state_signature: str | None
    active_claim_expires_at_ms: int | None
    last_delivered_at_ms: int | None


@dataclass(frozen=True, slots=True)
class KnowledgePromptProjectionInputs:
    delivery: KnowledgePromptDeliveryRecord | None
    pending_events: tuple[KnowledgePromptEventRecord, ...]
    rag_config: JSONDict | None
    rag_counts: JSONDict
    latest_documents: tuple[JSONDict, ...]


@dataclass(frozen=True, slots=True)
class KnowledgePromptClaimResult:
    claimed: bool
    claim_id: str | None
    request_id: str | None
    event_ceiling_id: int | None
    state_signature: str | None


@dataclass(frozen=True, slots=True)
class KnowledgePromptDeliveryClaim:
    conv_id: str
    user_id: int
    claim_id: str
    request_id: str
    event_ceiling_id: int
    state_signature: str
