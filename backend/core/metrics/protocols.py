"""SoAI - Core metrics protocols [backend/core/metrics/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol

if TYPE_CHECKING:
    from core.metrics.usage import ModalityUsageRecord
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DatabaseMetricsProtocol",
    "MetricsManagerProtocol",
    "MetricsRecorderProtocol",
    "TokenStreamMetricsProtocol",
)


class MetricsRecorderProtocol(Protocol):
    def increment_counter(self, *keys: str, value: int = 1) -> None: ...

    def set_gauge(self, *keys: str, value: float) -> None: ...

    def record_timing(self, *keys: str, duration_ms: float) -> None: ...

    def record_historical_metric(
        self,
        metric_key: str,
        value: float,
        observed_at_ms: int | None = None,
    ) -> None: ...

    def record_unique(self, *keys: str, item: str | float) -> None: ...

    def record_tokens_for_billing(
        self,
        plugin: str,
        model_id: str,
        client_id: str,
        tokens: int,
    ) -> None: ...

    def record_completion_tokens(
        self,
        plugin: str,
        tokens: int,
    ) -> None: ...

    def update_download_speed_metrics(
        self,
        bytes_per_second: float,
        source: str = "real_download",
    ) -> None: ...

    def increment_genesis_request(self) -> None: ...

    def purge_plugin_metrics(self, plugin_name: str) -> None: ...


class TokenStreamMetricsProtocol(Protocol):
    def begin_token_stream(self, stream_id: str, plugin: str) -> None: ...

    def record_token_stream_delta(
        self,
        stream_id: str,
        plugin: str,
        token_delta: int,
    ) -> None: ...

    def finish_token_stream(self, stream_id: str) -> None: ...


class MetricsManagerProtocol(MetricsRecorderProtocol, TokenStreamMetricsProtocol, Protocol):
    @property
    def config(self) -> ConfigProtocol: ...

    history_config: dict[str, JSONValue]

    @property
    def interval(self) -> int | None: ...

    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def reset_metrics(self) -> None: ...

    async def get_capabilities(self) -> JSONDict: ...

    async def get_all_metrics(self) -> JSONDict: ...

    def record_modality_usage(self, record: ModalityUsageRecord) -> None: ...

    async def get_historical_data(
        self,
        metric_key: str,
        start_ts_ms: int,
        end_ts_ms: int,
        points: int = 300,
        interval_ms: int | None = None,
        aggregation: str = "avg",
    ) -> JSONDict: ...


class DatabaseMetricsProtocol(Protocol):
    core: DatabaseCoreProtocol

    async def upsert_live_metrics(self, metrics: list[tuple[str, str, int]]) -> None: ...

    async def get_all_live_metrics(self) -> list[JSONDict]: ...

    async def clear_all_live_metrics(self) -> None: ...

    async def get_context_compaction_metric_totals(self) -> JSONDict: ...

    async def log_historical_metrics(self, metrics_snapshot: dict[str, int | float]) -> None: ...

    async def log_historical_metric(
        self,
        metric_key: str,
        value: float,
        observed_at_ms: int | None,
    ) -> None: ...

    async def prune_old_historical_metrics(self, retention_hours: int) -> None: ...

    async def get_genesis_data(self) -> JSONDict: ...

    async def update_genesis_uptime(self, delta_ms: int) -> None: ...

    async def increment_genesis_counters(self, requests_delta: int, tokens_delta: int) -> None: ...

    async def reset_genesis_counters(self) -> None: ...

    async def reset_genesis_uptime(self) -> None: ...

    async def initialize_genesis(self, now_ts_ms: int) -> None: ...

    async def get_historical_metrics_data_aggregated(
        self,
        metric_key: str,
        start_ts_ms: int,
        end_ts_ms: int,
        interval_ms: int,
        aggregation: str,
        max_points: int,
    ) -> JSONDict: ...
