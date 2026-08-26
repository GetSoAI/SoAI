"""SoAI - Metrics manager public operations [backend/metrics/manager/public_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.metrics.usage import ModalityUsageRecord
from core.types.json import JSONDict
from metrics.manager.internal_protocols import (
    MetricsOperationSurfaceOwnerProtocol,
    MetricsQuerySurfaceProtocol,
    MetricsServiceMethodSurfaceProtocol,
)
from metrics.manager.operation_surface import (
    begin_token_stream,
    finish_token_stream,
    record_completion_tokens,
    record_token_stream_delta,
    record_tokens_for_billing,
)
from metrics.manager.query_surface import (
    MetricsHistoryMethodRequest,
    get_all_metrics_method,
    get_capabilities_method,
    get_historical_data_method,
)
from metrics.manager.service_methods import (
    broadcast_metrics_method,
    flatten_and_flush_metrics_method,
    flush_genesis_deltas_method,
    increment_counter_method,
    increment_genesis_request_method,
    purge_plugin_metrics_method,
    record_historical_metric_method,
    record_modality_usage_method,
    record_timing_method,
    record_unique_method,
    rehydrate_from_db_method,
    reset_metrics_method,
    set_gauge_method,
    snapshot_metrics_method,
    update_download_speed_metrics_method,
)
from metrics.manager.types import MetricsTree, MetricsWorkerArg

__all__ = ("MetricsManagerOperations",)


class MetricsManagerOperations:
    async def get_capabilities(self: MetricsQuerySurfaceProtocol) -> JSONDict:
        return await get_capabilities_method(self)

    async def get_all_metrics(self: MetricsQuerySurfaceProtocol) -> JSONDict:
        return await get_all_metrics_method(self)

    async def get_historical_data(
        self: MetricsQuerySurfaceProtocol,
        metric_key: str,
        start_ts_ms: int,
        end_ts_ms: int,
        points: int = 300,
        interval_ms: int | None = None,
        aggregation: str = "avg",
    ) -> JSONDict:
        return await get_historical_data_method(
            self,
            MetricsHistoryMethodRequest(
                metric_key,
                start_ts_ms,
                end_ts_ms,
                points,
                interval_ms,
                aggregation,
            ),
        )

    def increment_counter(
        self: MetricsOperationSurfaceOwnerProtocol,
        *keys: str,
        value: int = 1,
    ) -> None:
        increment_counter_method(self, *keys, value=value)

    def set_gauge(
        self: MetricsOperationSurfaceOwnerProtocol,
        *keys: str,
        value: float,
    ) -> None:
        set_gauge_method(self, *keys, value=value)

    def record_timing(
        self: MetricsOperationSurfaceOwnerProtocol,
        *keys: str,
        duration_ms: float,
    ) -> None:
        record_timing_method(self, *keys, duration_ms=duration_ms)

    def record_historical_metric(
        self: MetricsOperationSurfaceOwnerProtocol,
        metric_key: str,
        value: float,
        observed_at_ms: int | None = None,
    ) -> None:
        record_historical_metric_method(self, metric_key, value, observed_at_ms=observed_at_ms)

    def record_unique(
        self: MetricsOperationSurfaceOwnerProtocol,
        *keys: str,
        item: MetricsWorkerArg,
    ) -> None:
        record_unique_method(self, *keys, item=item)

    def record_tokens_for_billing(
        self: MetricsOperationSurfaceOwnerProtocol,
        plugin: str,
        model_id: str,
        client_id: str,
        tokens: int,
    ) -> None:
        record_tokens_for_billing(
            self,
            plugin,
            model_id,
            client_id,
            tokens,
        )

    def begin_token_stream(
        self: MetricsOperationSurfaceOwnerProtocol,
        stream_id: str,
        plugin: str,
    ) -> None:
        begin_token_stream(self, stream_id, plugin)

    def record_completion_tokens(
        self: MetricsOperationSurfaceOwnerProtocol,
        plugin: str,
        tokens: int,
    ) -> None:
        record_completion_tokens(self, plugin, tokens)

    def record_token_stream_delta(
        self: MetricsOperationSurfaceOwnerProtocol,
        stream_id: str,
        plugin: str,
        token_delta: int,
    ) -> None:
        record_token_stream_delta(self, stream_id, plugin, token_delta)

    def finish_token_stream(
        self: MetricsOperationSurfaceOwnerProtocol,
        stream_id: str,
    ) -> None:
        finish_token_stream(self, stream_id)

    def record_modality_usage(
        self: MetricsOperationSurfaceOwnerProtocol,
        record: ModalityUsageRecord,
    ) -> None:
        record_modality_usage_method(self, record)

    def update_download_speed_metrics(
        self: MetricsOperationSurfaceOwnerProtocol,
        bytes_per_second: float,
        source: str = "real_download",
    ) -> None:
        update_download_speed_metrics_method(self, bytes_per_second, source=source)

    def increment_genesis_request(self: MetricsOperationSurfaceOwnerProtocol) -> None:
        increment_genesis_request_method(self)

    def purge_plugin_metrics(self: MetricsOperationSurfaceOwnerProtocol, plugin_name: str) -> None:
        purge_plugin_metrics_method(self, plugin_name)

    async def _snapshot_metrics(self: MetricsQuerySurfaceProtocol) -> MetricsTree:
        return await snapshot_metrics_method(self)

    async def _flush_genesis_deltas(self: MetricsServiceMethodSurfaceProtocol) -> None:
        await flush_genesis_deltas_method(self)

    async def _flatten_and_flush_metrics(self: MetricsServiceMethodSurfaceProtocol) -> None:
        await flatten_and_flush_metrics_method(self)

    async def _rehydrate_from_db(self: MetricsServiceMethodSurfaceProtocol) -> None:
        await rehydrate_from_db_method(self)

    async def reset_metrics(self: MetricsServiceMethodSurfaceProtocol) -> None:
        await reset_metrics_method(self)

    async def _broadcast_metrics(self: MetricsServiceMethodSurfaceProtocol) -> None:
        await broadcast_metrics_method(self)
