"""SoAI - Database I/O logging and file-size snapshots [backend/database/core/file_monitoring_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.validation.booleans import parse_bool

__all__ = (
    "is_io_logging_enabled",
    "snapshot_db_file_sizes",
)

LOGGER_NAME = "SoAI.database.core.file_monitoring_support"
OPERATION = "database.monitoring.is_io_logging_enabled"
OPERATION_SNAPSHOT_DB_FILE_SIZES = "database.monitoring.snapshot_db_file_sizes"


def is_io_logging_enabled(config: ConfigProtocol) -> bool:
    try:
        return bool(
            parse_bool(config.get("DATA.DATABASE.METRICS.IO_LOGGING", False), default=False),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to parse IO_LOGGING flag (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return False


def snapshot_db_file_sizes(db_file_paths: tuple[str, str, str]) -> dict[str, int]:
    logger = get_logger(LOGGER_NAME)
    sizes: dict[str, int] = {}
    for path in db_file_paths:
        try:
            sizes[path] = os.path.getsize(path)
        except FileNotFoundError:
            sizes[path] = 0
        except OSError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Skipped tracking database file size.",
                operation=OPERATION_SNAPSHOT_DB_FILE_SIZES,
                details={"path": path},
                level="debug",
            )
    return sizes
