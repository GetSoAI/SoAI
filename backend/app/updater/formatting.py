"""SoAI - Updater logging formatting [backend/app/updater/formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import sys

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.configuration_constants import DEFAULT_LOG_DATE_FORMAT, DEFAULT_LOG_FORMAT
from core.logging.formatters import UnifiedFormatter
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger

__all__ = ("setup_logging",)

LOGGER_NAME = "SoAI.app.updater.formatting"
OPERATION = "application_updater.setup_logger"


def setup_logging(log_file_path: str, level: int = logging.INFO) -> StandardLogger:
    logger = get_logger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    formatter = UnifiedFormatter(
        DEFAULT_LOG_FORMAT,
        DEFAULT_LOG_DATE_FORMAT,
        use_colors=False,
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    previous_handlers = list(logger.handlers)
    logger.handlers = [console_handler]
    for previous_handler in previous_handlers:
        previous_handler.close()
    try:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to create file log handler",
            operation=OPERATION,
            details={"path": log_file_path},
        )
    return logger
