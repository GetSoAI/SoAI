"""SoAI - Hardware variant support speed template builders [backend/hardware/variant_support_speed_templates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.hardware.protocols import DatabaseHardwareProtocol
from core.hardware.protocols_speed_test import (
    DiskSpeedTestServiceProtocol,
    NetworkSpeedTestServiceProtocol,
)
from core.hardware.speed_test.disk_speed_test_types import SpeedTestSnapshot
from core.hardware.speed_test.types import NetworkSpeedTestSnapshot
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.types.protocols import HttpClientProtocol
from core.validation.numbers import coerce_float_from_json

__all__ = (
    "build_speed_template",
    "collect_disk_speed_template",
    "collect_network_speed_template",
    "unknown_speed_template",
)

LOGGER_NAME = "SoAI.hardware.variant_support_speed_templates"
OPERATION_REAL_DOWNLOAD_SPEED_TEMPLATE = "hardware.variant_support.real_download_speed_template"
OPERATION_NETWORK_SPEED_TEMPLATE = "hardware.variant_support.network_speed_template"
SPEED_TEST_LOAD_FACTOR: float = 1.2


def build_speed_template(
    snapshot: SpeedTestSnapshot | NetworkSpeedTestSnapshot,
    *,
    mode: str,
    estimation_factor: float,
    storage_path: str | None = None,
) -> JSONDict | None:
    if snapshot is None:
        return None
    try:
        observed_unix = snapshot.observed_unix
    except AttributeError:
        observed_unix = None
    try:
        duration_ms = snapshot.duration_ms
    except AttributeError:
        duration_ms = None
    try:
        bytes_downloaded = snapshot.bytes_downloaded
    except AttributeError:
        bytes_downloaded = None
    try:
        bytes_per_second = snapshot.bytes_per_second
    except AttributeError:
        bytes_per_second = None
    if isinstance(snapshot, NetworkSpeedTestSnapshot):
        sample_bytes = None
    else:
        sample_bytes = snapshot.sample_bytes
    payload: JSONDict = {
        "status": "ready",
        "observed_at_ms": (int(float(observed_unix) * 1000) if observed_unix else None),
        "duration_ms": duration_ms,
        "bytes_downloaded": bytes_downloaded,
        "bytes_per_second": bytes_per_second,
        "mode": mode,
        "sample_bytes": sample_bytes,
        "estimation_factor": estimation_factor,
    }
    if payload["mode"] == "disk_read" and payload["sample_bytes"] is None:
        payload["sample_bytes"] = payload["bytes_downloaded"]
    if storage_path is not None:
        storage_value = storage_path
    elif isinstance(snapshot, NetworkSpeedTestSnapshot):
        storage_value = None
    else:
        storage_value = snapshot.storage_path
    if storage_value is not None:
        payload["storage_path"] = storage_value
    return payload


def unknown_speed_template(
    *,
    mode: str,
    estimation_factor: float,
    storage_path: str | None = None,
    interface: str | None = None,
) -> JSONDict:
    payload: JSONDict = {
        "status": "unavailable",
        "mode": mode,
        "observed_at_ms": None,
        "duration_ms": None,
        "bytes_downloaded": None,
        "bytes_per_second": None,
        "sample_bytes": None,
        "estimation_factor": estimation_factor,
        "detail": "Speed measurements unavailable",
    }
    if storage_path is not None:
        payload["storage_path"] = storage_path
    if interface is not None:
        payload["interface"] = interface
    return payload


async def collect_disk_speed_template(
    storage_path: str | None,
    include_speed_tests: bool,
    *,
    database_hardware: DatabaseHardwareProtocol | None,
    disk_speed_test_service: DiskSpeedTestServiceProtocol,
    require_measurements: bool,
) -> JSONDict | None:
    logger = get_logger(LOGGER_NAME)
    estimation_factor = SPEED_TEST_LOAD_FACTOR
    if not include_speed_tests:
        return (
            unknown_speed_template(
                mode="disk_read",
                estimation_factor=estimation_factor,
                storage_path=storage_path,
            )
            if require_measurements
            else None
        )
    if not storage_path:
        return (
            unknown_speed_template(
                mode="disk_read",
                estimation_factor=estimation_factor,
                storage_path=None,
            )
            if require_measurements
            else None
        )
    try:
        snapshot = await disk_speed_test_service.get_cached_snapshot(
            storage_path,
            database_hardware,
            900.0,
        )
        if snapshot is None:
            snapshot = await disk_speed_test_service.get_snapshot(
                storage_path,
                database_hardware,
                900.0,
                32 * MIB_BYTES,
            )
        template = build_speed_template(
            snapshot,
            mode="disk_read",
            estimation_factor=estimation_factor,
            storage_path=storage_path,
        )
        if template is not None:
            return template
    except (OSError, RuntimeError, ValueError, SoAIError) as exception:
        logger.trace(
            "Disk speed template collection failed for '%s': %s",
            storage_path,
            str(exception),
        )
    return (
        unknown_speed_template(
            mode="disk_read",
            estimation_factor=estimation_factor,
            storage_path=storage_path,
        )
        if require_measurements
        else None
    )


async def collect_network_speed_template(
    include_speed_tests: bool,
    *,
    database_hardware: DatabaseHardwareProtocol | None,
    http_client: HttpClientProtocol | None,
    network_speed_test_service: NetworkSpeedTestServiceProtocol,
    require_measurements: bool,
) -> JSONDict | None:
    logger = get_logger(LOGGER_NAME)
    estimation_factor = 1.0
    if not include_speed_tests:
        return (
            unknown_speed_template(mode="network_download", estimation_factor=estimation_factor)
            if require_measurements
            else None
        )
    if database_hardware is not None:
        try:
            get_median_real_download_speed = database_hardware.get_median_real_download_speed
        except AttributeError:
            get_median_real_download_speed = None
    else:
        get_median_real_download_speed = None
    if callable(get_median_real_download_speed):
        try:
            record = await get_median_real_download_speed()
        except (OSError, RuntimeError, ValueError, SoAIError) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to read median real download speed.",
                operation=OPERATION_REAL_DOWNLOAD_SPEED_TEMPLATE,
                level="trace",
            )
            record = None
        if isinstance(record, Mapping):
            throughput = coerce_float_from_json(record.get("bytes_per_second"), default=None)
            if throughput is not None and throughput > 0:
                observed_at_ms = (
                    coerce_float_from_json(record.get("observed_at_ms"), default=None) or epoch_ms()
                )
                return {
                    "status": "ready",
                    "observed_at_ms": int(observed_at_ms),
                    "duration_ms": None,
                    "bytes_downloaded": None,
                    "bytes_per_second": throughput,
                    "mode": "real_download",
                    "sample_bytes": None,
                    "estimation_factor": estimation_factor,
                }
    if http_client is None:
        return (
            unknown_speed_template(mode="network_download", estimation_factor=estimation_factor)
            if require_measurements
            else None
        )
    try:
        snapshot = await network_speed_test_service.get_snapshot(http_client=http_client)
        template = build_speed_template(
            snapshot,
            mode="network_download",
            estimation_factor=estimation_factor,
        )
        if template is not None:
            return template
    except (OSError, RuntimeError, ValueError, SoAIError) as exception:
        log_handled_exception(
            logger,
            exception,
            message="Network speed template collection failed.",
            operation=OPERATION_NETWORK_SPEED_TEMPLATE,
            level="trace",
        )
    return (
        unknown_speed_template(mode="network_download", estimation_factor=estimation_factor)
        if require_measurements
        else None
    )
