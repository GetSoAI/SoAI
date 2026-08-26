"""SoAI - Disk speed snapshot loading and caching [backend/hardware/monitoring/disk_speed_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from concurrent import futures
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.state.errors import DatabaseUnavailableError
from core.validation.coercion import coerce_float, coerce_int
from hardware.internal_protocols import DiskSpeedManagerProtocol
from hardware.variant_support_speed_templates import SPEED_TEST_LOAD_FACTOR

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_disk_speed_snapshot",)

OPERATION = "hardware.get_disk_speed_snapshot"
SCHEDULE_REFRESH_EXCEPTIONS: tuple[type[Exception], ...] = (
    RuntimeError,
    ValueError,
    *RECOVERABLE_EXCEPTIONS,
)


def _build_disk_speed_payload(record: JSONDict | None) -> JSONDict | None:
    if not record:
        return None
    bytes_per_second = coerce_float(record.get("bytes_per_second"))
    bytes_processed = coerce_int(record.get("bytes_processed"))
    duration_ms = coerce_int(record.get("duration_ms"))
    has_positive_rate = bool(bytes_per_second and bytes_per_second > 0)
    has_positive_bytes = bool(bytes_processed and bytes_processed > 0)
    has_positive_duration = bool(duration_ms and duration_ms > 0)
    if not (has_positive_rate and has_positive_bytes and has_positive_duration):
        return None
    observed_at_ms = coerce_int(record.get("observed_at_ms"))
    sample_bytes = coerce_int(record.get("sample_bytes") or record.get("bytes_processed"))
    return {
        "status": "ready",
        "detail": None,
        "observed_at_ms": observed_at_ms if observed_at_ms and observed_at_ms > 0 else None,
        "duration_ms": duration_ms,
        "bytes_downloaded": bytes_processed,
        "bytes_per_second": bytes_per_second,
        "estimated_ms": None,
        "base_estimated_ms": None,
        "size_bytes": None,
        "mode": "disk_read",
        "sample_bytes": (sample_bytes if sample_bytes and sample_bytes > 0 else None),
        "storage_path": record.get("path"),
        "estimation_factor": SPEED_TEST_LOAD_FACTOR,
        "cache_key": record.get("cache_key"),
    }


def _schedule_disk_speed_refresh(manager: DiskSpeedManagerProtocol) -> None:
    database_hardware = manager.database_hardware
    loop = manager.main_loop
    if (
        database_hardware is None
        or loop is None
        or loop.is_closed()
        or manager.state.monitoring_stop_event.is_set()
    ):
        return
    coroutine = database_hardware.get_latest_speed_test_snapshot()
    try:
        manager.state.disk_speed_refresh_future = asyncio.run_coroutine_threadsafe(
            coroutine,
            loop,
        )
    except SCHEDULE_REFRESH_EXCEPTIONS as exception:
        coroutine.close()
        log_exception(
            manager.logger,
            exception,
            message="Failed to schedule disk speed snapshot cache refresh",
            operation=OPERATION,
        )


def _consume_completed_disk_speed_refresh(
    manager: DiskSpeedManagerProtocol,
    future: futures.Future[JSONDict | None],
    *,
    cached_at: float,
) -> None:
    try:
        record = future.result()
    except futures.CancelledError:
        return
    except DatabaseUnavailableError:
        manager.logger.debug(
            "Skipping disk speed snapshot load because database is unavailable.",
        )
        manager.set_disk_speed_cache(manager.cached_disk_speed, cached_at=cached_at)
        return
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            manager.logger,
            exception,
            message="Failed to load disk speed snapshot",
            operation=OPERATION,
        )
        manager.set_disk_speed_cache(manager.cached_disk_speed, cached_at=cached_at)
        return
    payload = _build_disk_speed_payload(record)
    manager.set_disk_speed_cache(payload, cached_at=cached_at)


def get_disk_speed_snapshot(manager: DiskSpeedManagerProtocol) -> JSONDict | None:
    now = time.monotonic()
    with manager.state.cache_lock:
        future = manager.state.disk_speed_refresh_future
        if future is not None and future.done():
            manager.state.disk_speed_refresh_future = None
            _consume_completed_disk_speed_refresh(manager, future, cached_at=now)
        if now - manager.disk_speed_cache_timestamp < 30:
            return manager.cached_disk_speed
        if manager.state.disk_speed_refresh_future is None:
            _schedule_disk_speed_refresh(manager)
        return manager.cached_disk_speed
