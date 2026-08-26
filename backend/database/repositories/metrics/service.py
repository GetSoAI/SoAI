"""SoAI - Database metrics service [backend/database/repositories/metrics/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.timing.epoch import epoch_ms
from database.core.data_conversions import validate_retention_hours
from database.core.flags import FEATURE_METRICS
from database.core.operations import sync_prune_by_timestamp
from database.repositories.metrics.genesis import (
    get_genesis_data_query,
    sync_increment_genesis_counters,
    sync_initialize_genesis,
    sync_reset_genesis_counters,
    sync_reset_genesis_uptime,
    sync_update_genesis_uptime,
)
from database.repositories.metrics.history.repository import (
    get_historical_metrics_data_aggregated,
)
from database.repositories.metrics.history.sync_logging import (
    sync_log_historical_metric,
    sync_log_historical_metrics,
)
from database.repositories.metrics.live import (
    get_all_live_metrics_query,
    sync_clear_all_live_metrics,
    sync_upsert_live_metrics,
)
from database.repositories.users.context_compaction_metric_events import (
    get_context_compaction_metric_totals_query,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMetrics",)


class DatabaseMetrics:
    core: DatabaseCoreProtocol
    config: ConfigProtocol
    fernet: tuple[Fernet, ...]

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.config = deps.config
        self.fernet = deps.fernet

    async def upsert_live_metrics(self, metrics: list[tuple[str, str, int]]) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(sync_upsert_live_metrics, metrics)

    async def get_all_live_metrics(self) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        return await self.core.reader.execute_read(get_all_live_metrics_query)

    async def clear_all_live_metrics(self) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(sync_clear_all_live_metrics)

    async def get_context_compaction_metric_totals(self) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        return await self.core.reader.execute_read(get_context_compaction_metric_totals_query)

    async def log_historical_metrics(self, metrics_snapshot: dict[str, int | float]) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(sync_log_historical_metrics, metrics_snapshot)

    async def log_historical_metric(
        self,
        metric_key: str,
        value: float,
        observed_at_ms: int | None,
    ) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        timestamp_ms = epoch_ms() if observed_at_ms is None else observed_at_ms
        await self.core.writer.queue_write_operation(
            sync_log_historical_metric,
            metric_key,
            value,
            timestamp_ms,
        )

    async def prune_old_historical_metrics(self, retention_hours: int) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        sanitized_retention = validate_retention_hours(retention_hours)
        await self.core.writer.queue_write_operation(
            sync_prune_by_timestamp,
            ("metrics_history",),
            sanitized_retention,
        )

    async def get_genesis_data(self) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        return await self.core.reader.execute_read(get_genesis_data_query)

    async def update_genesis_uptime(self, delta_ms: int) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(
            sync_update_genesis_uptime,
            delta_ms,
        )

    async def increment_genesis_counters(self, requests_delta: int, tokens_delta: int) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(
            sync_increment_genesis_counters,
            requests_delta,
            tokens_delta,
        )

    async def reset_genesis_counters(self) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(
            sync_reset_genesis_counters,
        )

    async def reset_genesis_uptime(self) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(
            sync_reset_genesis_uptime,
        )

    async def initialize_genesis(self, now_ts_ms: int) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        await self.core.writer.queue_write_operation(
            sync_initialize_genesis,
            now_ts_ms,
        )

    async def get_historical_metrics_data_aggregated(
        self,
        metric_key: str,
        start_ts_ms: int,
        end_ts_ms: int,
        interval_ms: int,
        aggregation: str,
        max_points: int,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_METRICS)
        return await self.core.reader.execute_read(
            get_historical_metrics_data_aggregated,
            metric_key,
            start_ts_ms,
            end_ts_ms,
            interval_ms,
            aggregation,
            max_points,
        )
