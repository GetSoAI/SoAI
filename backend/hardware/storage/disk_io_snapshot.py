"""SoAI - Optional disk I/O acquisition and device counter projection [backend/hardware/storage/disk_io_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.validation.integers import coerce_non_negative_exact_int_or_none

if TYPE_CHECKING:
    from core.platform.protocols import PsutilDiskIOCountersProtocol
    from core.types.json import JSONDict

OPERATION_HARDWARE_STORAGE_GET_DISK_INFO = "hardware_storage.get_disk_info"
OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_DISK_IO_COUNTERS = (
    "hardware_storage.get_disk_info.disk_io_counters"
)


__all__ = (
    "DISK_QUERY_EXCEPTIONS",
    "LOGGER_NAME",
    "DiskIOCollection",
    "DiskIOSnapshot",
    "collect_disk_io_counters",
    "find_disk_io_entry",
    "project_disk_io_counters",
)

DISK_QUERY_EXCEPTIONS: tuple[type[Exception], ...] = (OSError,) + RECOVERABLE_EXCEPTIONS

LOGGER_NAME = "SoAI.hardware.storage.disk_io_snapshot"


@dataclass(frozen=True, slots=True)
class DiskIOCollection:
    counters: Mapping[str, PsutilDiskIOCountersProtocol]
    available: bool


@dataclass(frozen=True, slots=True)
class DiskIOSnapshot:
    values: JSONDict
    malformed: bool


def collect_disk_io_counters() -> DiskIOCollection:
    try:
        counters = psutil.disk_io_counters(perdisk=True)
    except DISK_QUERY_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to query disk I/O counters (non-critical).",
            operation=OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_DISK_IO_COUNTERS,
            level="trace",
        )
        return DiskIOCollection({}, False)
    return DiskIOCollection(counters or {}, counters is not None)


def find_disk_io_entry(
    device: str | None,
    device_meta: JSONDict | None,
    io_stats: Mapping[str, PsutilDiskIOCountersProtocol],
) -> PsutilDiskIOCountersProtocol | None:
    candidates: list[str] = []
    if isinstance(device, str) and device:
        candidates.append(device)
        try:
            if basename := os.path.basename(device):
                candidates.append(basename)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to normalize partition device basename (non-critical).",
                operation=OPERATION_HARDWARE_STORAGE_GET_DISK_INFO,
                details={"device": device},
                level="debug",
            )
    if isinstance(device_meta, dict):
        for key in ("kname", "path", "name"):
            value = device_meta.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
    for candidate in candidates:
        normalized = candidate if candidate.startswith("/dev/") else f"/dev/{candidate}"
        if io_entry := io_stats.get(candidate) or io_stats.get(normalized):
            return io_entry
    return None


def project_disk_io_counters(counter: PsutilDiskIOCountersProtocol) -> DiskIOSnapshot:
    try:
        read_bytes = counter.read_bytes
    except AttributeError:
        read_bytes = None
    try:
        write_bytes = counter.write_bytes
    except AttributeError:
        write_bytes = None
    try:
        read_count = counter.read_count
    except AttributeError:
        read_count = None
    try:
        write_count = counter.write_count
    except AttributeError:
        write_count = None
    try:
        read_time = counter.read_time
    except AttributeError:
        read_time = None
    try:
        write_time = counter.write_time
    except AttributeError:
        write_time = None
    try:
        busy_time = counter.busy_time
    except AttributeError:
        busy_time = None
    values: JSONDict = {}
    malformed = False
    for key, value in (
        ("read_bytes", read_bytes),
        ("write_bytes", write_bytes),
        ("read_count", read_count),
        ("write_count", write_count),
        ("read_time_ms", read_time),
        ("write_time_ms", write_time),
        ("busy_time_ms", busy_time),
    ):
        if value is None:
            if key != "busy_time_ms":
                malformed = True
            continue
        normalized = coerce_non_negative_exact_int_or_none(value)
        if normalized is None:
            malformed = True
        else:
            values[key] = normalized
    return DiskIOSnapshot(values, malformed)
