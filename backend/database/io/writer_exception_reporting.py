"""SoAI - Database writer exception reporting [backend/database/io/writer_exception_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.logging.protocols import LoggerProtocol

__all__ = ("report_database_writer_runtime_exception",)


def report_database_writer_runtime_exception(
    *,
    logger: LoggerProtocol,
    exception: BaseException,
    message: str,
    operation: str,
    level: str,
) -> SoAIError:
    coerced = coerce_to_soai_error(
        exception,
        operation="database_core.writer_thread",
    )
    log_exception(
        logger,
        coerced,
        message=message,
        operation=operation,
        level=level,
    )
    return coerced
