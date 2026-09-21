"""SoAI - Database hardware service [backend/database/repositories/hardware/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.hardware.soaibench_publication import SoAIBenchPublicationRecord
from core.timing.epoch import epoch_ms
from database.core.data_conversions import validate_retention_hours
from database.core.operations import sync_prune_by_timestamp
from database.repositories.dependencies import DatabaseRepositoryDependencies
from database.repositories.hardware.history import (
    get_historical_hardware_data_aggregated,
)
from database.repositories.hardware.history_reset import sync_clear_hardware_history
from database.repositories.hardware.history_tables import HARDWARE_HISTORY_TABLES
from database.repositories.hardware.logging import sync_log_hardware_metrics
from database.repositories.hardware.soaibench import (
    get_soaibench_run_for_user_query,
    sync_create_soaibench_run,
    sync_finish_soaibench_run,
    sync_reconcile_soaibench_running_rows,
    sync_request_soaibench_stop,
    sync_update_soaibench_heartbeat,
)
from database.repositories.hardware.soaibench_history import (
    list_soaibench_history_export_query,
    list_soaibench_history_query,
    list_soaibench_recent_for_user_query,
)
from database.repositories.hardware.soaibench_history_deletion import (
    sync_delete_soaibench_local_run,
)
from database.repositories.hardware.soaibench_publication_records import (
    materialize_soaibench_publication_record,
)
from database.repositories.hardware.soaibench_publications import (
    get_soaibench_publication_query,
    sync_finish_soaibench_publication,
    sync_prepare_soaibench_publication,
)
from database.repositories.hardware.speed import (
    SpeedTestWritePayload,
    get_latest_network_speed_snapshot_query,
    get_latest_speed_test_snapshot_query,
    get_median_real_download_speed_query,
    get_speed_test_query,
    sync_insert_real_download_speed,
    sync_upsert_speed_test,
)

if TYPE_CHECKING:
    from core.hardware.soaibench_persistence import (
        SoAIBenchMutationResult,
        SoAIBenchReconciliationResult,
    )
    from core.types.json import JSONDict

__all__ = ("DatabaseHardware",)


class DatabaseHardware:
    core: DatabaseCoreProtocol
    config: ConfigProtocol

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.config = deps.config

    async def log_hardware_metrics(self, info: JSONDict) -> None:
        await self.core.writer.queue_write_operation(
            sync_log_hardware_metrics,
            info,
        )

    async def prune_old_hardware_metrics(self, retention_hours: int) -> None:
        sanitized_retention = validate_retention_hours(retention_hours)
        await self.core.writer.queue_write_operation(
            sync_prune_by_timestamp,
            HARDWARE_HISTORY_TABLES,
            sanitized_retention,
        )

    async def clear_hardware_history(self) -> None:
        await self.core.writer.queue_write_operation(
            sync_clear_hardware_history,
        )

    async def get_latest_network_speed_snapshot(self) -> JSONDict:
        return await self.core.reader.execute_read(get_latest_network_speed_snapshot_query)

    async def get_latest_speed_test_snapshot(self) -> JSONDict | None:
        return await self.core.reader.execute_read(get_latest_speed_test_snapshot_query)

    async def upsert_speed_test(
        self,
        cache_key: str,
        path: str,
        sample_bytes: int,
        observed_at_ms: int,
        duration_ms: int,
        bytes_processed: int,
        bytes_per_second: float,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_upsert_speed_test,
            SpeedTestWritePayload(
                cache_key=cache_key,
                path=path,
                sample_bytes=sample_bytes,
                observed_at_ms=observed_at_ms,
                duration_ms=duration_ms,
                bytes_processed=bytes_processed,
                bytes_per_second=bytes_per_second,
            ),
        )

    async def get_speed_test(self, cache_key: str) -> JSONDict | None:
        return await self.core.reader.execute_read(get_speed_test_query, cache_key)

    async def save_real_download_speed(
        self,
        plugin_name: str,
        model_id: str,
        bytes_downloaded: int,
        duration_ms: int,
        bytes_per_second: float,
    ) -> None:
        observed_at_ms = epoch_ms()
        await self.core.writer.queue_write_operation(
            sync_insert_real_download_speed,
            plugin_name,
            model_id,
            bytes_downloaded,
            duration_ms,
            bytes_per_second,
            observed_at_ms,
        )

    async def get_median_real_download_speed(self) -> JSONDict | None:
        return await self.core.reader.execute_read(get_median_real_download_speed_query)

    async def get_historical_hardware_data(
        self,
        component: str,
        start_ts_ms: int,
        end_ts_ms: int,
        interval_ms: int,
        aggregation: str,
        max_points: int,
        identifier: str | None = None,
    ) -> JSONDict:
        return await self.core.reader.execute_read(
            get_historical_hardware_data_aggregated,
            component,
            start_ts_ms,
            end_ts_ms,
            interval_ms,
            aggregation,
            max_points,
            identifier,
        )

    async def create_soaibench_run(self, run: JSONDict) -> SoAIBenchMutationResult:
        return await self.core.writer.queue_write_operation(
            sync_create_soaibench_run,
            run,
        )

    async def update_soaibench_heartbeat(
        self,
        *,
        run_id: str,
        last_heartbeat_at_ms: int,
        sample_count: int,
        summary_json: str | None,
    ) -> SoAIBenchMutationResult:
        return await self.core.writer.queue_write_operation(
            sync_update_soaibench_heartbeat,
            run_id,
            last_heartbeat_at_ms,
            sample_count,
            summary_json,
        )

    async def finish_soaibench_run(
        self,
        run_id: str,
        fields: JSONDict,
    ) -> SoAIBenchMutationResult:
        return await self.core.writer.queue_write_operation(
            sync_finish_soaibench_run,
            run_id,
            fields,
        )

    async def request_soaibench_stop(
        self,
        *,
        user_id: int,
        run_id: str,
        stop_requested_at_ms: int,
    ) -> SoAIBenchMutationResult:
        return await self.core.writer.queue_write_operation(
            sync_request_soaibench_stop,
            user_id,
            run_id,
            stop_requested_at_ms,
        )

    async def get_soaibench_run_for_user(
        self,
        *,
        user_id: int,
        run_id: str,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            get_soaibench_run_for_user_query,
            user_id,
            run_id,
        )

    async def list_soaibench_history(
        self,
        *,
        user_id: int,
        identity: JSONDict,
        limit: int,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_soaibench_history_query,
            user_id=user_id,
            identity=identity,
            limit=limit,
        )

    async def list_soaibench_history_export(
        self,
        *,
        user_id: int,
        identity: JSONDict,
    ) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_soaibench_history_export_query,
            user_id=user_id,
            identity=identity,
        )

    async def list_soaibench_recent_for_user(self, *, user_id: int, limit: int) -> list[JSONDict]:
        return await self.core.reader.execute_read(
            list_soaibench_recent_for_user_query,
            user_id=user_id,
            limit=limit,
        )

    async def reconcile_soaibench_running_rows(
        self,
        completed_at_ms: int,
    ) -> SoAIBenchReconciliationResult:
        return await self.core.writer.queue_write_operation(
            sync_reconcile_soaibench_running_rows,
            completed_at_ms,
        )

    async def delete_soaibench_local_run(self, *, run_id: str, user_id: int) -> None:
        await self.core.writer.queue_write_operation(
            sync_delete_soaibench_local_run, run_id, user_id
        )

    async def get_soaibench_publication(
        self,
        *,
        user_id: int,
        run_id: str,
    ) -> SoAIBenchPublicationRecord | None:
        publication = await self.core.reader.execute_read(
            get_soaibench_publication_query,
            user_id,
            run_id,
        )
        return (
            None if publication is None else materialize_soaibench_publication_record(publication)
        )

    async def prepare_soaibench_publication(
        self,
        *,
        user_id: int,
        run_id: str,
        canonical_submission_json: str,
        prepared_at_ms: int,
    ) -> SoAIBenchPublicationRecord:
        publication = await self.core.writer.queue_write_operation(
            sync_prepare_soaibench_publication,
            run_id,
            user_id,
            canonical_submission_json,
            prepared_at_ms,
        )
        return materialize_soaibench_publication_record(publication)

    async def finish_soaibench_publication(
        self,
        *,
        user_id: int,
        run_id: str,
        receipt_json: str,
        published_at_ms: int,
    ) -> SoAIBenchPublicationRecord:
        publication = await self.core.writer.queue_write_operation(
            sync_finish_soaibench_publication,
            run_id,
            user_id,
            receipt_json,
            published_at_ms,
        )
        return materialize_soaibench_publication_record(publication)
