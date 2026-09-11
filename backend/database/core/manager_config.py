"""SoAI - Database manager configuration parsing [backend/database/core/manager_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses

from core.config.default_schema.database_manager import DEFAULT_VACUUM_INTERVAL_HOURS
from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = (
    "DatabaseManagerSettings",
    "resolve_database_manager_settings",
)

OPERATION = "database.manager_config.resolve_database_manager_settings"


@dataclasses.dataclass(frozen=True, slots=True)
class DatabaseManagerSettings:
    sqlite_connect_timeout: float
    writer_init_timeout: float
    writer_shutdown_timeout: float
    writer_sample_interval: float
    writer_operation_timeout: float
    vacuum_interval_hours: int
    read_pool_max_size: int
    read_mmap_size_mb: int
    write_mmap_size_mb: int


def resolve_database_manager_settings(
    config: ConfigProtocol,
    *,
    logger: LoggerProtocol,
) -> DatabaseManagerSettings:
    def _resolve_manager_float(key: str, default: float, minimum: float) -> float:
        raw_value = config.get(f"DATA.DATABASE.{key}", default)
        try:
            return coerce_positive_float(raw_value, default=default, minimum=minimum)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Invalid DATA.DATABASE config value; using default.",
                operation=OPERATION,
                details={
                    "key": key,
                    "raw_value": str(raw_value),
                    "default": default,
                },
                level="warning",
            )
            return float(default)

    def _resolve_manager_int(
        key: str,
        default: int,
        minimum: int,
        maximum: int | None,
    ) -> int:
        raw_value = config.get(f"DATA.DATABASE.{key}", default)
        try:
            if isinstance(raw_value, bool):
                raise TypeError("Boolean values are not supported for integer config entries.")
            return coerce_positive_int(
                raw_value,
                default=default,
                minimum=minimum,
                maximum=maximum,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Invalid DATA.DATABASE config value; using default.",
                operation=OPERATION,
                details={
                    "key": key,
                    "raw_value": str(raw_value),
                    "default": default,
                },
                level="warning",
            )
            return int(default)

    sqlite_connect_timeout = _resolve_manager_float("SQLITE.CONNECT_TIMEOUT_SEC", 10.0, 0.1)
    writer_init_timeout = _resolve_manager_float("WRITER.INIT_TIMEOUT_SEC", 30.0, 0.1)
    writer_shutdown_timeout = _resolve_manager_float("WRITER.SHUTDOWN_TIMEOUT_SEC", 5.0, 0.1)
    writer_sample_interval = _resolve_manager_float("METRICS.IO_SAMPLE_INTERVAL_SEC", 1.0, 0.1)
    writer_operation_timeout = _resolve_manager_float("WRITER.OPERATION_TIMEOUT_SEC", 120.0, 1.0)
    raw_vacuum_hours = _resolve_manager_float(
        "SQLITE.VACUUM_INTERVAL_HOURS", float(DEFAULT_VACUUM_INTERVAL_HOURS), 0.0
    )
    read_pool_max_size = _resolve_manager_int("SQLITE.READ_POOL_MAX_SIZE", 8, 1, 512)
    read_mmap_size_mb = _resolve_manager_int("SQLITE.READ_MMAP_SIZE_MB", 4096, 0, 4096)
    write_mmap_size_mb = _resolve_manager_int("SQLITE.WRITE_MMAP_SIZE_MB", 4096, 0, 4096)
    vacuum_interval_hours = (
        0
        if raw_vacuum_hours <= 0
        else coerce_positive_int(raw_vacuum_hours, default=DEFAULT_VACUUM_INTERVAL_HOURS, minimum=1)
    )
    return DatabaseManagerSettings(
        sqlite_connect_timeout=sqlite_connect_timeout,
        writer_init_timeout=writer_init_timeout,
        writer_shutdown_timeout=writer_shutdown_timeout,
        writer_sample_interval=writer_sample_interval,
        writer_operation_timeout=writer_operation_timeout,
        vacuum_interval_hours=vacuum_interval_hours,
        read_pool_max_size=read_pool_max_size,
        read_mmap_size_mb=read_mmap_size_mb,
        write_mmap_size_mb=write_mmap_size_mb,
    )
