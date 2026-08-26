"""SoAI - Orchestrator execution internal protocols [backend/orchestrator/execution/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from typing import TYPE_CHECKING, Protocol

from core.errors.error_types import ErrorType
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.tasks.task import Task
from orchestrator.execution.active_inferences import ActiveInferenceInfo
from orchestrator.execution.streaming_completion import StreamingCompletion

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict

__all__ = (
    "ActiveInferenceRegistryProtocol",
    "CancelTaskCallable",
    "DeliveryManagerProtocol",
    "ExecutorEngineProtocol",
    "FailTaskCallable",
    "InferencePayloadPreparerProtocol",
    "InflightCancellationManagerProtocol",
    "OutcomeManagerProtocol",
    "ResultProcessorProtocol",
    "SucceedTaskCallable",
)


class ActiveInferenceRegistryProtocol(Protocol):
    async def register(self, tracking_id: str, info: ActiveInferenceInfo) -> None: ...

    async def pop(self, tracking_id: str) -> ActiveInferenceInfo | None: ...

    async def get(self, tracking_id: str) -> ActiveInferenceInfo | None: ...

    async def update_progress(self, tracking_id: str) -> None: ...

    async def set_dispatch_time(self, tracking_id: str, dispatch_time: float) -> None: ...

    async def set_request_timeout(self, tracking_id: str, timeout: float) -> None: ...

    async def get_dispatch_time(self, tracking_id: str) -> float | None: ...

    async def list_for_plugin(self, plugin_name: str) -> list[ActiveInferenceInfo]: ...

    async def count_for_plugin(self, plugin_name: str) -> int: ...

    async def has_tracking_id(self, tracking_id: str) -> bool: ...

    async def tasks(self) -> list[asyncio.Task[bool]]: ...

    async def snapshot(self) -> list[JSONDict]: ...


class DeliveryManagerProtocol(Protocol):
    async def prepare_delivery(self, task: Task) -> tuple[Task, int | None]: ...

    async def clear_delivery_in_progress(self, task: Task, delivery_version: int) -> bool: ...


class InferencePayloadPreparerProtocol(Protocol):
    async def prepare_inference_payload_for_plugin(
        self,
        task: Task,
        plugin_name: str,
        model_info: JSONDict | None,
    ) -> JSONDict: ...


class ResultProcessorProtocol(Protocol):
    def update_config(
        self,
        health_check_config: JSONDict,
        conservative_billing_threshold: float,
    ) -> None: ...

    def handle_unary_result(
        self,
        task: Task,
        model_info: JSONDict,
        result: JSONDict,
        *,
        plugin_name: str,
    ) -> JSONDict: ...

    async def handle_streaming_result(
        self,
        task: Task,
        model_info: JSONDict,
        result: AsyncIterable[StreamChunk],
        *,
        usage_reporting_requested: bool,
        plugin_name: str,
    ) -> StreamingCompletion | JSONDict | None: ...

    async def buffer_stream_to_result(
        self,
        task: Task,
        model_info: JSONDict,
        result: AsyncIterable[StreamChunk],
        *,
        plugin_name: str,
    ) -> JSONDict: ...


class OutcomeManagerProtocol(Protocol):
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

    async def fail_task(
        self,
        task: Task,
        reason: str,
        *,
        allow_failover: bool = True,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
        reason_is_public: bool = False,
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


class SucceedTaskCallable(Protocol):
    async def __call__(
        self,
        task: Task,
        *,
        result: JSONDict | None = None,
        is_streaming: bool = False,
        streaming_completion: StreamingCompletion | JSONDict | None = None,
    ) -> None: ...


class CancelTaskCallable(Protocol):
    async def __call__(
        self,
        task: Task,
        reason: str,
        *,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
    ) -> None: ...


class FailTaskCallable(Protocol):
    async def __call__(
        self,
        task: Task,
        reason: str,
        *,
        allow_failover: bool = True,
        error_type: ErrorType = ErrorType.SERVER_ERROR,
        reason_is_public: bool = False,
    ) -> None: ...


class ExecutorEngineProtocol(Protocol):
    def update_config(self, health_check_config: JSONDict) -> None: ...

    async def execute_task(
        self,
        task: Task,
        plugin_instance: PluginInstanceProtocol,
        model_info: JSONDict,
    ) -> bool: ...


class InflightCancellationManagerProtocol(Protocol):
    def cancel_inflight(
        self,
        info: ActiveInferenceInfo | None,
        *,
        prefix: str,
        reason: str,
    ) -> None: ...

    def fail_inflight(
        self,
        info: ActiveInferenceInfo | None,
        *,
        prefix: str,
        reason: str,
        allow_failover: bool,
        error_type: ErrorType,
    ) -> None: ...

    def has_cleanup_intent(self, tracking_id: str) -> bool: ...
