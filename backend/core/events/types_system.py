"""SoAI - System lifecycle and configuration event type definitions [backend/core/events/types_system.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from core.events.types_base import (
    Event,
    EventDelivery,
    ReplyableUserCommand,
    UserCommand,
)
from core.events.types_conversation import (
    ChatStreamActivityChangedEvent,
    ChatStreamEvent,
    ChatStreamStatusPreviewEvent,
    ConversationAttachmentChangedEvent,
    ConversationCreatedEvent,
    ConversationDeletedEvent,
    ConversationDraftChangedEvent,
    ConversationInputsChangedEvent,
    ConversationUpdatedEvent,
    KnowledgeAttachmentChangedEvent,
    MessageSavedEvent,
    ModelTestStreamEvent,
    ThinkingTailCompletedEvent,
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallLiveUpdatedEvent,
    ToolCallOutputDeltaEvent,
    ToolCallStartedEvent,
)
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ChatStreamActivityChangedEvent",
    "ChatStreamEvent",
    "ChatStreamStatusPreviewEvent",
    "ConfigReloadedEvent",
    "ConversationAttachmentChangedEvent",
    "ConversationCreatedEvent",
    "ConversationDeletedEvent",
    "ConversationDraftChangedEvent",
    "ConversationUpdatedEvent",
    "DomainEventOutboxDispatchRequestedEvent",
    "GPUActiveSlotChangedEvent",
    "GPUBootPreferenceChangedEvent",
    "GPUCapabilitiesChangedEvent",
    "GPUSavedSettingsChangedEvent",
    "GPUStartupWarningEvent",
    "HardwareSnapshotUpdatedEvent",
    "KnowledgeAttachmentChangedEvent",
    "MessageSavedEvent",
    "MetricsUpdatedEvent",
    "ModelTestStreamEvent",
    "ConversationInputsChangedEvent",
    "ProcessListUpdatedEvent",
    "PowerOperationChangedEvent",
    "SoAIBenchRunUpdatedEvent",
    "SoAIMainState",
    "SystemQuiesceEvent",
    "SystemRestartRequestedEvent",
    "SystemRestartRequiredEvent",
    "ThinkingTailCompletedEvent",
    "ToolCallCompletedEvent",
    "ToolCallCreatedEvent",
    "ToolCallLiveUpdatedEvent",
    "ToolCallOutputDeltaEvent",
    "ToolCallStartedEvent",
)


class SoAIMainState(Enum):
    STARTING = "starting"
    READY = "ready"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass(slots=True)
class SystemQuiesceEvent(Event):
    reason: str = "System preparing for shutdown"


@dataclass(slots=True)
class SystemRestartRequestedEvent(Event):
    reason: str = "System restart requested"


@dataclass(slots=True)
class DomainEventOutboxDispatchRequestedEvent(Event):
    delivery: EventDelivery = EventDelivery.DROPPABLE


@dataclass(slots=True)
class GPUCapabilitiesChangedEvent(Event):
    capabilities: JSONDict


@dataclass(slots=True)
class GPUSavedSettingsChangedEvent(Event):
    device_id: str
    slots: JSONDict
    boot: JSONDict
    live: JSONDict


@dataclass(slots=True)
class GPUActiveSlotChangedEvent(Event):
    device_id: str
    slot: str | None
    signature: str | None
    applied_at: str | None


@dataclass(slots=True)
class GPUBootPreferenceChangedEvent(Event):
    device_id: str
    boot: JSONDict


@dataclass(slots=True)
class GPUStartupWarningEvent(Event):
    device_ids: list[str]
    message: str


@dataclass(slots=True)
class HardwareSnapshotUpdatedEvent(Event):
    snapshot: JSONDict
    delivery: EventDelivery = EventDelivery.DROPPABLE


@dataclass(slots=True)
class ProcessListUpdatedEvent(Event):
    processes: list[JSONDict]
    delivery: EventDelivery = EventDelivery.DROPPABLE


@dataclass(slots=True)
class SoAIBenchRunUpdatedEvent(Event):
    user_id: int
    device_id: str
    run_id: str
    update_seq: int
    update_type: str
    run: JSONDict
    delivery: EventDelivery = EventDelivery.MUST_DELIVER


@dataclass(slots=True)
class MetricsUpdatedEvent(Event):
    metrics: JSONDict
    delivery: EventDelivery = EventDelivery.DROPPABLE


@dataclass(slots=True)
class SystemRestartRequiredEvent(Event):
    reason: str
    changed_path: str


@dataclass(slots=True)
class PowerOperationChangedEvent(Event):
    operation_id: str
    owner_id: int
    action: str
    force: bool
    accepted_at_ms: int
    execute_at_ms: int
    status: str
    attempt_count: int
    dispatch_started_at_ms: int | None
    completed_at_ms: int | None
    result_code: str | None
    error_code: str | None


@dataclass(slots=True)
class ConfigReloadedEvent(Event):
    config_name: str
    path: str
    config_dict: JSONDict
    content_hash: str | None
    source: str
    revision: int
    changed_keys: frozenset[str] = field(default_factory=frozenset[str])


@dataclass(slots=True)
class ConfigReloadFailedEvent(Event):
    config_name: str
    path: str
    error: str
    content_hash: str | None
    source: str


@dataclass(slots=True)
class ConfigRemovedEvent(Event):
    config_name: str
    path: str
    source: str


@dataclass(slots=True)
class ConfigAppliedEvent(Event):
    config_name: str
    path: str
    content_hash: str | None
    source: str


@dataclass(slots=True)
class ConfigApplyFailedEvent(Event):
    config_name: str
    path: str
    content_hash: str | None
    source: str
    error: str


@dataclass(slots=True)
class SoAIMainStateChangedEvent(Event):
    new_state: SoAIMainState
    previous_state: SoAIMainState


@dataclass(slots=True)
class SystemMainStateOverrideEvent(Event):
    state: SoAIMainState
    duration_sec: int
    reason: str


@dataclass(slots=True)
class TriggerConfigReconciliationCommand(UserCommand):
    reason: str
    context: RequestContext | None = None


@dataclass(slots=True)
class TriggerConfigScanCommand(UserCommand):
    reason: str
    config_name: str | None = None


@dataclass(slots=True)
class UpdateConfigCommand(ReplyableUserCommand):
    config_name: str
    new_data: JSONDict
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdateConfigResultEvent(Event):
    success: bool
    config_name: str
    changed_keys: tuple[str, ...] = ()
    error: str | None = None
