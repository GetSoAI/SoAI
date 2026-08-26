"""SoAI - Metrics manager internal protocols [backend/metrics/manager/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.concurrency.task_groups import ManagedTaskGroup

if TYPE_CHECKING:
    import asyncio

    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.metrics.protocols import DatabaseMetricsProtocol
    from core.runtime.protocols import ServiceLifecycleProtocol
    from core.tasks.protocols import TaskCancellationBinderProtocol
    from core.types.json import JSONDict
    from metrics.manager.operations import MetricsQueueFullThrottle
    from metrics.manager.types import MetricsTree, MetricsWorkerQueueItem

__all__ = (
    "DownloadSpeedDatabaseProtocol",
    "ManagedTaskGroupOwnerProtocol",
    "MetricsOperationSurfaceOwnerProtocol",
    "MetricsQuerySurfaceProtocol",
    "MetricsServiceMethodSurfaceProtocol",
    "TokenRateCalculatorProtocol",
)


class ManagedTaskGroupOwnerProtocol(Protocol):
    managed_task_group: ManagedTaskGroup | None


class TokenRateCalculatorProtocol(Protocol):
    def begin_stream(
        self,
        stream_id: str,
        plugin: str,
        observed_at_ms: int,
    ) -> None: ...

    def record_stream_delta(
        self,
        stream_id: str,
        plugin: str,
        token_delta: int,
        observed_at_ms: int,
    ) -> None: ...

    def record_completion_tokens(
        self,
        plugin: str,
        tokens: int,
        observed_at_ms: int,
    ) -> None: ...

    def finish_stream(self, stream_id: str, observed_at_ms: int) -> None: ...

    def get_rates(
        self,
        now_ms: int,
    ) -> dict[str, dict[str, float | int] | dict[str, dict[str, float | int]]]: ...

    def reset(self) -> None: ...


class DownloadSpeedDatabaseProtocol(Protocol):
    async def get_median_real_download_speed(self) -> JSONDict | None: ...


class MetricsQuerySurfaceProtocol(Protocol):
    lock: asyncio.Lock
    history_config: JSONDict
    history_enabled: bool
    token_rate_calculator: TokenRateCalculatorProtocol
    database_metrics: DatabaseMetricsProtocol

    @property
    def metrics_ref(self) -> list[MetricsTree]: ...

    @property
    def capabilities_cache(self) -> JSONDict | None: ...

    @capabilities_cache.setter
    def capabilities_cache(self, value: JSONDict | None) -> None: ...

    @property
    def capabilities_cache_timestamp(self) -> float: ...

    @capabilities_cache_timestamp.setter
    def capabilities_cache_timestamp(self, value: float) -> None: ...

    @property
    def session_start_time_monotonic_ms(self) -> int: ...

    async def snapshot_metrics(self) -> MetricsTree: ...
    async def get_capabilities(self) -> JSONDict: ...


class MetricsOperationSurfaceOwnerProtocol(Protocol):
    background_queue: asyncio.Queue[MetricsWorkerQueueItem] | None
    accepting_operations: bool
    queue_full_throttle: MetricsQueueFullThrottle
    token_rate_calculator: TokenRateCalculatorProtocol


class MetricsServiceMethodSurfaceProtocol(
    MetricsQuerySurfaceProtocol,
    MetricsOperationSurfaceOwnerProtocol,
    Protocol,
):
    config: ConfigProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    event_bus: EventBusProtocol | None
    lifecycle: ServiceLifecycleProtocol
    background_worker_task: asyncio.Task[None] | None
    genesis_flush_lock: asyncio.Lock
    genesis_requests_delta: list[int]
    genesis_tokens_delta: list[int]
    session_start_time_ms: int

    async def background_worker(self) -> None: ...
    async def get_all_metrics(self) -> JSONDict: ...
