"""SoAI - Disk speed test service with caching [backend/core/hardware/speed_test/disk_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
import os
import time
from dataclasses import dataclass

from core.config.byte_sizes import MIB_BYTES
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.hardware.protocols import DatabaseHardwareProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.hardware.speed_test.disk_speed_test_measurement import (
    measure_disk_speed,
    resolve_existing_path,
    speed_test_key,
)
from core.hardware.speed_test.disk_speed_test_snapshot_parsing import (
    build_snapshot_from_db_record,
    is_record_fresh,
)
from core.hardware.speed_test.disk_speed_test_types import SpeedTestSnapshot
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms, epoch_seconds_float
from core.validation.coercion import coerce_float_with_bool, coerce_int_from_scalar

__all__ = (
    "DiskSpeedTestService",
    "DiskSpeedTestServiceDependencies",
    "SpeedTestSnapshot",
)

LOGGER_NAME = "SoAI.core.hardware.disk_service"
OPERATION = "core.hardware.speed_test.disk_service.get_snapshot"


_SPEED_TEST_CACHE_SECONDS = 900.0
_SPEED_TEST_SAMPLE_BYTES = 32 * MIB_BYTES
_SPEED_TEST_BLOCK_BYTES = 4 * MIB_BYTES


@dataclass(frozen=True, slots=True)
class DiskSpeedTestServiceDependencies:
    reservation_provider: StorageManagerProtocol
    cache_ttl_seconds: float = _SPEED_TEST_CACHE_SECONDS
    sample_bytes: int = _SPEED_TEST_SAMPLE_BYTES
    block_bytes: int = _SPEED_TEST_BLOCK_BYTES

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DiskSpeedTestServiceDependencies",
            block_bytes=self.block_bytes,
            cache_ttl_seconds=self.cache_ttl_seconds,
            reservation_provider=self.reservation_provider,
            sample_bytes=self.sample_bytes,
        )


class DiskSpeedTestService:
    __slots__ = ("_block_bytes", "_cache", "_cache_ttl", "_locks", "_reservation_provider")

    def __init__(self, deps: DiskSpeedTestServiceDependencies) -> None:
        self._cache: dict[str, SpeedTestSnapshot] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._cache_ttl: float = deps.cache_ttl_seconds
        self._block_bytes: int = deps.block_bytes
        self._reservation_provider = deps.reservation_provider

    def _get_lock_for(self, cache_key: str) -> asyncio.Lock:
        lock = self._locks.get(cache_key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[cache_key] = lock
        return lock

    async def get_cached_snapshot(
        self,
        storage_path: str,
        database_hardware: DatabaseHardwareProtocol | None,
        cache_seconds: float,
    ) -> SpeedTestSnapshot | None:
        if not storage_path:
            return None
        resolved_path = resolve_existing_path(storage_path)
        if not resolved_path:
            return None
        target_directory = (
            resolved_path if os.path.isdir(resolved_path) else os.path.dirname(resolved_path)
        )
        if not target_directory:
            return None
        cache_key = speed_test_key(target_directory)
        now_monotonic = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and now_monotonic - cached.observed_monotonic < cache_seconds:
            return cached
        if database_hardware is None:
            return cached
        try:
            record = await database_hardware.get_speed_test(cache_key)
        except (OSError, RuntimeError, ValueError, SoAIError):
            record = None
        if not record:
            return cached
        snapshot = build_snapshot_from_db_record(
            record,
            cache_key=cache_key,
            storage_path=target_directory,
            observed_monotonic=now_monotonic,
        )
        if snapshot is None:
            return cached
        self._cache[cache_key] = snapshot
        return snapshot

    async def get_snapshot(
        self,
        storage_path: str,
        database_hardware: DatabaseHardwareProtocol | None,
        cache_seconds: float,
        sample_bytes: int,
    ) -> SpeedTestSnapshot:
        if not storage_path:
            raise ValidationError("Storage path is required for speed test.")
        resolved_path = resolve_existing_path(storage_path)
        if not resolved_path:
            raise ValidationError("Storage path does not exist for speed test.")
        target_directory = (
            resolved_path if os.path.isdir(resolved_path) else os.path.dirname(resolved_path)
        )
        if not target_directory:
            raise ValidationError("Storage path does not provide a directory for speed test.")
        cache_key = speed_test_key(target_directory)
        lock = self._get_lock_for(cache_key)
        async with lock:
            now_monotonic = time.monotonic()
            cached = self._cache.get(cache_key)
            if cached and now_monotonic - cached.observed_monotonic < cache_seconds:
                return cached
            now_ts_ms = int(epoch_ms())
            if database_hardware is not None:
                try:
                    record = await database_hardware.get_speed_test(cache_key)
                except (OSError, RuntimeError, ValueError, SoAIError):
                    record = None
                if record:
                    observed_at_ms_value = coerce_int_from_scalar(record.get("observed_at_ms", 0))
                    observed_at_ms = (
                        int(observed_at_ms_value) if observed_at_ms_value is not None else 0
                    )
                    if is_record_fresh(
                        now_ms=now_ts_ms,
                        observed_at_ms=observed_at_ms,
                        cache_seconds=cache_seconds,
                    ):
                        duration_ms_value = coerce_int_from_scalar(record.get("duration_ms", 0))
                        bytes_downloaded = coerce_int_from_scalar(record.get("bytes_processed", 0))
                        bytes_per_second = coerce_float_with_bool(record.get("bytes_per_second", 0))
                        if (
                            duration_ms_value is None
                            or bytes_downloaded is None
                            or bytes_per_second is None
                        ):
                            duration_ms_value = 0
                            bytes_downloaded = 0
                            bytes_per_second = 0
                        if (
                            duration_ms_value > 0
                            and bytes_downloaded > 0
                            and (bytes_per_second > 0)
                        ):
                            snapshot = SpeedTestSnapshot(
                                cache_key=cache_key,
                                storage_path=target_directory,
                                observed_monotonic=now_monotonic,
                                observed_unix=float(observed_at_ms) / 1000.0,
                                duration_ms=int(duration_ms_value),
                                bytes_downloaded=bytes_downloaded,
                                bytes_per_second=bytes_per_second,
                                sample_bytes=int(sample_bytes),
                            )
                            self._cache[cache_key] = snapshot
                            return snapshot
            try:
                total_bytes, duration = await asyncio.to_thread(
                    measure_disk_speed,
                    target_directory,
                    sample_bytes,
                    self._block_bytes,
                    self._reservation_provider,
                )
            except (OSError, RuntimeError, ValueError) as exception:
                raise StateError(f"Disk speed test failed: {exception}") from exception
            bytes_per_second = total_bytes / duration
            if not math.isfinite(bytes_per_second) or bytes_per_second <= 0:
                raise StateError("Disk speed test produced invalid throughput.")
            now_unix = epoch_seconds_float()
            observed_at_ms = int(now_unix * 1000)
            duration_ms = max(0, int(duration * 1000))
            snapshot = SpeedTestSnapshot(
                cache_key=cache_key,
                storage_path=target_directory,
                observed_monotonic=time.monotonic(),
                observed_unix=now_unix,
                duration_ms=duration_ms,
                bytes_downloaded=int(total_bytes),
                bytes_per_second=float(bytes_per_second),
                sample_bytes=int(sample_bytes),
            )
            self._cache[cache_key] = snapshot
            if database_hardware is not None:
                try:
                    await database_hardware.upsert_speed_test(
                        cache_key,
                        target_directory,
                        sample_bytes,
                        observed_at_ms,
                        duration_ms,
                        int(total_bytes),
                        float(bytes_per_second),
                    )
                except (
                    OSError,
                    RuntimeError,
                    ValueError,
                    SoAIError,
                ) as exception:
                    log_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Failed to persist disk speed test result",
                        operation=OPERATION,
                        level="warning",
                    )
            return snapshot

    def invalidate_cache(self, storage_path: str | None = None) -> None:
        if storage_path is None:
            self._cache.clear()
            return
        resolved_path = resolve_existing_path(storage_path)
        if not resolved_path:
            return
        target_directory = (
            resolved_path if os.path.isdir(resolved_path) else os.path.dirname(resolved_path)
        )
        if target_directory:
            cache_key = speed_test_key(target_directory)
            self._cache.pop(cache_key, None)
