"""SoAI - SQLite database vacuum operations and scheduling [backend/database/core/vacuum.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
import sqlite3
import time
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after, deadline_remaining_clamped
from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isfile
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.formatting.time import format_duration_hhmm, format_interval_hours
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_dict
from core.sqlite.connections import connect_sqlite
from core.timing.durations import hours_to_seconds
from core.timing.epoch import epoch_seconds_float
from core.timing.formatting import timestamp_to_utc_iso
from core.validation.numbers import coerce_float_from_json
from database.core.wal_checkpoint import run_passive_wal_checkpoint
from database.internal_protocols import DatabaseVacuumCoreProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "load_last_vacuum_timestamp_from_disk",
    "persist_last_vacuum_timestamp_to_disk",
    "record_vacuum_timestamp",
    "resolve_vacuum_state_path",
    "sync_vacuum",
    "vacuum_loop",
)

LOGGER_NAME = "SoAI.database.core.vacuum"
OPERATION_DATABASE_CORE_VACUUM_LOAD_LAST_VACUUM_TIMESTAMP_FROM_DISK_ISFILE = (
    "database_core.vacuum.load_last_vacuum_timestamp_from_disk.isfile"
)
OPERATION_DATABASE_CORE_VACUUM_LOAD_LAST_VACUUM_TIMESTAMP_FROM_DISK_READ = (
    "database_core.vacuum.load_last_vacuum_timestamp_from_disk.read"
)
OPERATION_DATABASE_CORE_VACUUM_LOOP = "database_core.vacuum_loop"
OPERATION_DATABASE_CORE_VACUUM_PERSIST_LAST_VACUUM_TIMESTAMP_TO_DISK = (
    "database_core.vacuum.persist_last_vacuum_timestamp_to_disk"
)


def sync_vacuum(_connection: sqlite3.Connection, db_path: str) -> dict[str, int | float]:
    size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    start = time.monotonic()
    with connect_sqlite(
        db_path,
        timeout=5.0,
        uri=db_path.startswith("file:"),
    ) as vacuum_connection:
        vacuum_connection.execute("PRAGMA optimize")
        run_passive_wal_checkpoint(vacuum_connection)
        vacuum_connection.execute("VACUUM")
    elapsed = time.monotonic() - start
    size_after = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    return {
        "size_before": size_before,
        "size_after": size_after,
        "elapsed_sec": elapsed,
        "reclaimed": size_before - size_after,
    }


def resolve_vacuum_state_path(db_path: str, is_shared_memory_mode: bool) -> str | None:
    if is_shared_memory_mode:
        return None
    db_path_str = db_path.strip()
    if not db_path_str or db_path_str.startswith("file:"):
        return None
    return f"{db_path_str}.vacuum.json"


async def load_last_vacuum_timestamp_from_disk(
    state_path: str | None,
) -> float | None:
    logger = get_logger(LOGGER_NAME)
    if not state_path:
        return None
    try:
        if not await async_isfile(state_path):
            return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to check vacuum state file presence (non-critical).",
            operation=OPERATION_DATABASE_CORE_VACUUM_LOAD_LAST_VACUUM_TIMESTAMP_FROM_DISK_ISFILE,
            details={"state_path": state_path},
            level="debug",
        )
        return None

    def _sync_read() -> float | None:
        try:
            with open_text(state_path, encoding="utf-8") as handle:
                payload = parse_json_dict(handle.read(), field="database vacuum state")
        except (OSError, ValidationError):
            return None
        raw_ts = payload.get("last_vacuum_timestamp")
        if raw_ts is None:
            return None
        parsed = coerce_float_from_json(raw_ts, default=None)
        return parsed

    try:
        timestamp = await asyncio.to_thread(_sync_read)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read vacuum state file (non-critical).",
            operation=OPERATION_DATABASE_CORE_VACUUM_LOAD_LAST_VACUUM_TIMESTAMP_FROM_DISK_READ,
            details={"state_path": state_path},
            level="debug",
        )
        return None
    if timestamp is None:
        return None
    if timestamp <= 0:
        return None
    return timestamp


async def persist_last_vacuum_timestamp_to_disk(state_path: str | None, timestamp: float) -> None:
    logger = get_logger(LOGGER_NAME)
    if not state_path:
        return
    try:
        timestamp = float(timestamp)
    except (TypeError, ValueError):
        return
    if timestamp <= 0:
        return
    payload: JSONDict = {
        "last_vacuum_timestamp": int(timestamp),
        "last_vacuum_timestamp_iso": timestamp_to_utc_iso(timestamp),
    }

    def _sync_write(handle: io.TextIOBase) -> None:
        handle.write(serialize_json_pretty_sorted_strict(payload))
        handle.write("\n")

    try:
        await asyncio.to_thread(atomic_write_text, state_path, _sync_write)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to persist vacuum state (non-critical).",
            operation=OPERATION_DATABASE_CORE_VACUUM_PERSIST_LAST_VACUUM_TIMESTAMP_TO_DISK,
            level="debug",
        )


async def vacuum_loop(
    core: DatabaseVacuumCoreProtocol,
    vacuum_interval_hours: int,
    vacuum_shutdown_event: asyncio.Event,
    vacuum_schedule_changed_event: asyncio.Event,
) -> None:
    logger = get_logger(LOGGER_NAME)
    interval_sec = hours_to_seconds(vacuum_interval_hours)
    state_path = resolve_vacuum_state_path(core.db_path, core.is_shared_memory_mode)
    last_vacuum_timestamp = await load_last_vacuum_timestamp_from_disk(state_path)
    if last_vacuum_timestamp is None:
        last_vacuum_timestamp = epoch_seconds_float()
        await persist_last_vacuum_timestamp_to_disk(state_path, last_vacuum_timestamp)
    core.set_last_vacuum_timestamp(last_vacuum_timestamp)
    last_attempt_ts = float(last_vacuum_timestamp)
    now_unix = epoch_seconds_float()
    next_delay_sec = max(0.0, (last_attempt_ts + interval_sec) - now_unix)
    next_run_deadline_monotonic = deadline_after(next_delay_sec).deadline_monotonic
    logger.debug(
        "Periodic database vacuum task started (interval: %s, next vacuum in %s).",
        format_interval_hours(vacuum_interval_hours),
        format_duration_hhmm(next_delay_sec),
    )
    while not vacuum_shutdown_event.is_set():
        if vacuum_schedule_changed_event.is_set():
            vacuum_schedule_changed_event.clear()
            last_timestamp = core.last_vacuum_timestamp
            if last_timestamp is not None:
                last_attempt_ts = float(last_timestamp)
                now_unix = epoch_seconds_float()
                next_delay_sec = max(0.0, (last_attempt_ts + interval_sec) - now_unix)
                next_run_deadline_monotonic = deadline_after(next_delay_sec).deadline_monotonic
        delay_sec = deadline_remaining_clamped(next_run_deadline_monotonic)
        if delay_sec > 0:
            wait_reason = await wait_for_shutdown_or_schedule_change(
                vacuum_shutdown_event,
                vacuum_schedule_changed_event,
                delay_sec,
            )
            if wait_reason == "shutdown":
                break
            if wait_reason == "schedule_changed":
                last_timestamp = core.last_vacuum_timestamp
                if last_timestamp is not None:
                    last_attempt_ts = float(last_timestamp)
                now_unix = epoch_seconds_float()
                next_delay_sec = max(0.0, (last_attempt_ts + interval_sec) - now_unix)
                next_run_deadline_monotonic = deadline_after(next_delay_sec).deadline_monotonic
                continue
            if vacuum_shutdown_event.is_set():
                break
        attempt_ts = epoch_seconds_float()
        last_attempt_ts = float(attempt_ts)
        next_run_deadline_monotonic = deadline_after(float(interval_sec)).deadline_monotonic
        try:
            logger.info("Starting database vacuum...")
            result = await core.vacuum_database()
            reclaimed_mb = result["reclaimed"] / MIB_BYTES
            size_mb = result["size_after"] / MIB_BYTES
            logger.info(
                "Database vacuum completed in %.1fs. Size: %.1fMB, reclaimed: %.1fMB.",
                result["elapsed_sec"],
                size_mb,
                reclaimed_mb,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Database vacuum failed",
                operation=OPERATION_DATABASE_CORE_VACUUM_LOOP,
            )
    logger.debug("Database vacuum task stopped.")


async def record_vacuum_timestamp(
    core: DatabaseVacuumCoreProtocol,
    timestamp: float,
    vacuum_schedule_changed_event: asyncio.Event | None,
) -> None:
    try:
        timestamp = float(timestamp)
    except (TypeError, ValueError):
        return
    if timestamp <= 0:
        return
    core.set_last_vacuum_timestamp(timestamp)
    if vacuum_schedule_changed_event:
        vacuum_schedule_changed_event.set()
    state_path = resolve_vacuum_state_path(core.db_path, core.is_shared_memory_mode)
    await persist_last_vacuum_timestamp_to_disk(state_path, timestamp)
