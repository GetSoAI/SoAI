"""SoAI - Disk speed test measurement helpers [backend/core/hardware/speed_test/disk_speed_test_measurement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import time

from core.errors.exceptions import StateError
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary
from core.hardware.protocols_storage import (
    DiskSpaceReservationLeaseProtocol,
    StorageManagerProtocol,
)
from core.hardware.speed_test.files import open_for_speed_test

__all__ = (
    "ensure_speed_test_sample",
    "measure_disk_speed",
    "resolve_existing_path",
    "speed_test_key",
)

_SPEED_TEST_FILENAME = ".soai_disk_speed_test.bin"


def resolve_existing_path(
    path: str | bytes | os.PathLike[str] | os.PathLike[bytes] | None,
) -> str | None:
    if path is None:
        return None
    raw_path = os.fspath(path)
    if not isinstance(raw_path, str):
        return None
    candidate = os.path.abspath(raw_path)
    if not candidate:
        return None
    while True:
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(candidate)
        if not parent or parent == candidate:
            break
        candidate = parent
    return None


def speed_test_key(path: str) -> str:
    normalized = os.path.abspath(path)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def ensure_speed_test_sample(
    directory: str,
    sample_bytes: int,
    block_bytes: int,
    reservation_provider: StorageManagerProtocol,
) -> str:
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, _SPEED_TEST_FILENAME)
    regenerate = True
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) == sample_bytes:
            regenerate = False
    except OSError:
        regenerate = True
    if regenerate:
        with (
            _open_speed_sample_reservation(
                reservation_provider,
                file_path=file_path,
                sample_bytes=sample_bytes,
            ) as reservation,
            open_binary(file_path, mode="wb", buffering=0) as handle,
        ):
            remaining = sample_bytes
            chunk = os.urandom(min(block_bytes, sample_bytes))
            while remaining > 0:
                to_write = min(len(chunk), remaining)
                with reservation.claim_write_bytes(to_write) as claim:
                    handle.write(chunk[:to_write])
                    claim.commit()
                remaining -= to_write
            flush_and_fsync_file(handle)
    return file_path


def measure_disk_speed(
    directory: str,
    sample_bytes: int,
    block_bytes: int,
    reservation_provider: StorageManagerProtocol,
) -> tuple[int, float]:
    file_path = ensure_speed_test_sample(
        directory,
        sample_bytes,
        block_bytes,
        reservation_provider=reservation_provider,
    )
    with open_for_speed_test(file_path, block_bytes) as reader:
        start_time = time.perf_counter()
        total_bytes = 0
        while total_bytes < sample_bytes:
            chunk = reader.read(min(block_bytes, sample_bytes - total_bytes))
            if not chunk:
                break
            total_bytes += len(chunk)
        end_time = time.perf_counter()
    if total_bytes < sample_bytes:
        raise StateError("Disk speed test read incomplete sample.")
    duration = max(end_time - start_time, 1e-06)
    return (total_bytes, duration)


def _open_speed_sample_reservation(
    reservation_provider: StorageManagerProtocol,
    *,
    file_path: str,
    sample_bytes: int,
) -> DiskSpaceReservationLeaseProtocol:
    return reservation_provider.reserve_disk_space(
        path=file_path,
        required_bytes=sample_bytes,
        operation="core.hardware.speed_test.disk_sample",
        details={"sample_path": file_path},
    )
