"""SoAI - Core database request models for task persistence [backend/core/database/task_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.orchestrator.request_priority import RequestPriority
from core.runtime.request_sources import RequestSource

__all__ = (
    "ConversationInteractionCheckpointRequest",
    "CreateDurableInferenceTaskRequest",
    "CreateUnifiedTaskRequest",
    "DurableQueueClaim",
    "DurableQueueItemRequest",
    "UnifiedTaskFinalizationWriteResult",
    "UnifiedTaskQueryRequest",
    "durable_queue_claim_scheduling_key",
)


@dataclass(frozen=True, slots=True)
class ConversationInteractionCheckpointRequest:
    input_id: str
    conv_id: str
    user_id: int
    claim_generation: int
    claim_owner: str
    server_boot_id: str
    interaction_type: str
    suspension_phase: str
    iteration_index: int
    turn_id: str
    tool_call_id: str
    argument_hash: str | None
    reply_token: str
    focus_nonce: str
    expires_at_ms: int


@dataclass(frozen=True, slots=True)
class CreateUnifiedTaskRequest:
    task_id: str
    task_type: str
    status: str
    user_id: int
    owner_id: str
    owner_type: str
    ttl_ms: int | None
    poll_interval_ms: int
    progress_total: int | None
    metadata: str | None
    cancellation_id: str
    orchestration_state: str | None = None
    status_message: str | None = None
    max_concurrent: int | None = None
    interaction_checkpoint: ConversationInteractionCheckpointRequest | None = None


@dataclass(frozen=True, slots=True)
class DurableQueueClaim:
    task_id: str
    priority_order_at_ms: int
    enqueue_seq: int


@dataclass(frozen=True, slots=True)
class UnifiedTaskFinalizationWriteResult:
    updated: bool
    current_status: str | None
    completed_at_ms: int | None


def durable_queue_claim_scheduling_key(
    claim: DurableQueueClaim,
) -> tuple[int, int, str]:
    return (claim.priority_order_at_ms, claim.enqueue_seq, claim.task_id)


@dataclass(frozen=True, slots=True)
class DurableQueueItemRequest:
    task_id: str
    phase: str
    routing_key: str
    available_at_ms: int
    request_source: RequestSource
    delivery_mode: str
    request_priority: RequestPriority
    priority_order_at_ms: int
    plugin_name: str | None = None
    lease_owner: str | None = None
    lease_expires_at_ms: int | None = None
    attempt_count: int = 0
    dedup_hash: str | None = None
    dedup_lead_task_id: str | None = None


@dataclass(frozen=True, slots=True)
class CreateDurableInferenceTaskRequest:
    task: CreateUnifiedTaskRequest
    queue_item: DurableQueueItemRequest


@dataclass(frozen=True, slots=True)
class UnifiedTaskQueryRequest:
    user_id: int | None = None
    status: str | None = None
    task_type: str | None = None
    owner_type: str | None = None
    owner_id: str | None = None
    cancellation_id: str | None = None
    active_only: bool = False
    exclude_cancellation_requested: bool = False
    limit: int = 100
    offset: int = 0
