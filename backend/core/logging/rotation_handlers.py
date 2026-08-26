"""SoAI - Rotating log handler factory [backend/core/logging/rotation_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from collections.abc import Callable
from logging.handlers import TimedRotatingFileHandler

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.logging.configuration_constants import (
    DEFAULT_LOG_ROTATION_INTERVAL_COUNT,
    DEFAULT_LOG_ROTATION_UTC,
    DEFAULT_LOG_ROTATION_WHEN,
    DEFAULT_LOGS_COMPRESSION_SUFFIX,
)
from core.logging.formatter_support import ROOT_LOGGER_NAME
from core.logging.handlers.compressed_timed_rotating import (
    CompressedTimedRotatingHandler,
)

__all__ = ("create_rotation_handler",)


def create_rotation_handler(
    *,
    log_file: str,
    config: ConfigProtocol,
    formatter: logging.Formatter,
    encoding: str,
    get_int_config: Callable[[str, int], int],
) -> logging.FileHandler:
    if any(item in encoding for item in ("/", "\\")):
        message = f"Invalid log file encoding '{encoding}'."
        logging.getLogger(ROOT_LOGGER_NAME).error(message)
        raise ValidationError(message)
    compress_enabled = config.get_bool(
        "OBSERVABILITY.LOGGING.LOGGING_SYSTEM.MAIN_LOG_COMPRESS_LOGS",
    )
    backup_count = get_int_config("OBSERVABILITY.LOGGING.MAIN_LOG_BACKUP_COUNT", 5)
    file_handler: logging.FileHandler
    if compress_enabled:
        file_handler = CompressedTimedRotatingHandler(
            log_file,
            when=DEFAULT_LOG_ROTATION_WHEN,
            interval=DEFAULT_LOG_ROTATION_INTERVAL_COUNT,
            backupCount=backup_count,
            encoding=encoding,
            utc=DEFAULT_LOG_ROTATION_UTC,
            compress=True,
            compression_suffix=DEFAULT_LOGS_COMPRESSION_SUFFIX,
        )
    else:
        file_handler = TimedRotatingFileHandler(
            log_file,
            when=DEFAULT_LOG_ROTATION_WHEN,
            interval=DEFAULT_LOG_ROTATION_INTERVAL_COUNT,
            backupCount=backup_count,
            encoding=encoding,
            utc=DEFAULT_LOG_ROTATION_UTC,
        )
    file_handler.setFormatter(formatter)
    return file_handler
