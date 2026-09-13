"""SoAI - Orchestrator subsystem internal Protocol interfaces [backend/orchestrator/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from core.errors.error_types import ErrorType
from core.events.types_base import Event
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
    ImageEditRequestReceived,
    ImageVariationRequestReceived,
    InferenceRequestReceived,
)
from core.orchestrator.routing_config import ConstituentModelConfig, RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from orchestrator.capacity.slot_lease import PluginSlotLease

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.plugins.protocols_guardian import PluginGuardianProtocol
    from core.runtime.request_context import RequestContext
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from orchestrator.execution.streaming_completion import StreamingCompletion

__all__ = (
    "EnsurePluginQueueCallbackProtocol",
    "EventWithContextAndReplyProtocol",
    "FailWaitersCallable",
    "GuardianRefProtocol",
    "OrchestratorActiveInferenceProtocol",
    "OrchestratorCapacityProtocol",
    "OrchestratorHandlersProtocol",
    "OrchestratorInferenceExecutorProtocol",
    "OrchestratorTaskOutcomesProtocol",
    "PluginStateViewProtocol",
    "TransientFailureCooldownsProtocol",
    "VirtualModelHealthProtocol",
    "VirtualModelRotationProtocol",
)


class OrchestratorInferenceExecutorProtocol(Protocol):
    @property
    def routing_config(self) -> RoutingConfig: ...

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None: ...

    def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...

    async def execute_inference_on_task(
        self,
        task: Task,
        plugin_name: str,
        model_info: JSONDict,
    ) -> bool: ...


class OrchestratorTaskOutcomesProtocol(Protocol):
    async def fail_task(
        self,
        task: Task,
        reason: str,
        *,
        allow_failover: bool = True,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
        reason_is_public: bool = False,
    ) -> None: ...

    async def succeed_task(
        self,
        task: Task,
        *,
        result: JSONDict | None = None,
        is_streaming: bool = False,
        streaming_completion: StreamingCompletion | JSONDict | None = None,
    ) -> None: ...

    async def cancel_task(
        self,
        task: Task,
        reason: str,
        *,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None: ...

    async def fail_waiters(
        self,
        routing_key: str,
        reason: str,
        *,
        allow_failover: bool = True,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None: ...

    async def cancel_waiters(
        self,
        routing_key: str,
        reason: str,
        *,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None: ...


class FailWaitersCallable(Protocol):
    async def __call__(
        self,
        routing_key: str,
        reason: str,
        *,
        allow_failover: bool = True,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None: ...


class OrchestratorActiveInferenceProtocol(Protocol):
    async def cancel_inflight_task(self, tracking_id: str, reason: str) -> None: ...

    async def fail_inflight_task(
        self,
        tracking_id: str,
        reason: str,
        *,
        allow_failover: bool,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None: ...

    async def is_tracking_id_active(self, tracking_id: str) -> bool: ...

    async def fail_active_tasks(
        self,
        plugin_name: str,
        reason: str,
        *,
        allow_failover: bool,
        error_type: ErrorType,
    ) -> None: ...

    async def get_active_task_count(self, plugin_name: str) -> int: ...

    async def get_active_inference_tasks(self) -> list[asyncio.Task[bool]]: ...

    async def get_active_inferences_snapshot(self) -> list[JSONDict]: ...

    async def get_status_snapshot(self) -> JSONDict: ...


class OrchestratorHandlersProtocol(Protocol):
    async def handle_audio_transcription_request(
        self,
        event: AudioTranscriptionRequestReceived,
    ) -> InferenceRequestReceived | None: ...
    async def handle_audio_translation_request(
        self,
        event: AudioTranslationRequestReceived,
    ) -> InferenceRequestReceived | None: ...
    async def handle_image_edit_request(
        self,
        event: ImageEditRequestReceived,
    ) -> InferenceRequestReceived | None: ...
    async def handle_image_variation_request(
        self,
        event: ImageVariationRequestReceived,
    ) -> InferenceRequestReceived | None: ...


class OrchestratorCapacityProtocol(Protocol):
    async def acquire_plugin_slot(self, plugin_name: str) -> PluginSlotLease: ...
    async def ensure_plugin_capacity(
        self,
        plugin_name: str,
        plugin_limit: int,
        plugin_count: int,
    ) -> asyncio.Queue[Task]: ...
    async def get_existing_plugin_queue_binding(
        self,
        plugin_name: str,
    ) -> tuple[asyncio.Queue[Task], asyncio.Event] | None: ...
    async def enqueue_plugin_task(self, plugin_name: str, item: Task) -> None: ...
    async def get_queue_empty_snapshot(self, plugin_names: list[str]) -> dict[str, bool]: ...
    async def get_queue_sizes(self, plugin_names: list[str]) -> dict[str, int]: ...
    async def is_queue_empty(self, plugin_name: str) -> bool: ...
    async def drain_plugin_queue(self, plugin_name: str) -> list[Task]: ...
    async def update_concurrency_limits(
        self,
        limits: dict[str, int],
        *,
        plugin_count: int,
    ) -> None: ...
    def get_plugin_limit(self, plugin_name: str) -> int | None: ...
    def requires_plugin_capacity_refresh(self, plugin_name: str) -> bool: ...
    def get_plugin_queue_unlimited_workers(self) -> int: ...
    def get_plugin_queue_max_workers(self) -> int: ...
    def mark_plugin_capacity_stale(self, plugin_name: str) -> None: ...
    async def remove_plugin_capacity_state(self, plugin_name: str) -> None: ...
    async def get_status_snapshot(self) -> JSONDict: ...
    def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...


class TransientFailureCooldownsProtocol(Protocol):
    def update_cooldown(self, cooldown_seconds: float) -> None: ...
    def record(self, universal_id: str) -> None: ...
    def is_on_cooldown(self, universal_id: str) -> bool: ...
    def cleanup(self, logger: TraceLogger) -> int: ...


class VirtualModelHealthProtocol(Protocol):
    def update_cooldown(self, cooldown_seconds: float) -> None: ...
    async def record_success(self, virtual_model_name: str) -> None: ...
    async def record_failure(self, virtual_model_name: str) -> None: ...
    async def in_stale_cooldown(
        self,
        virtual_model_name: str,
        *,
        cleanup_expired: bool = True,
    ) -> bool: ...
    async def snapshot(self) -> dict[str, JSONDict]: ...
    async def prune(self, active_names: set[str]) -> None: ...


class VirtualModelRotationProtocol(Protocol):
    def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...
    async def select_next_candidate(
        self,
        virtual_model_name: str,
        models: Sequence[ConstituentModelConfig],
    ) -> list[ConstituentModelConfig]: ...
    async def prune(self, active_names: set[str]) -> None: ...


class GuardianRefProtocol(Protocol):
    value: PluginGuardianProtocol | None


class EnsurePluginQueueCallbackProtocol(Protocol):
    async def __call__(
        self,
        *,
        plugin_name: str,
        plugin_limit: int,
        plugin_count: int,
    ) -> asyncio.Queue[Task]: ...


class PluginStateViewProtocol(Protocol):
    active_tasks: set[str]


class EventWithContextAndReplyProtocol(Protocol):
    context: RequestContext
    reply_channel: asyncio.Queue[Event]
    required_capabilities: tuple[str, ...]
    required_modalities: tuple[str, ...]
