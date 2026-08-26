"""SoAI - Shared unexpected shutdown exception reporting helpers [backend/app/cli/unexpected_shutdown_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.protocols import LoggerProtocol

__all__ = (
    "coerce_and_log_unexpected_shutdown_exception",
    "coerce_and_log_unexpected_shutdown_exception_and_return_one",
)


def coerce_and_log_unexpected_shutdown_exception(
    logger: LoggerProtocol,
    exception: BaseException,
    *,
    message: str,
    operation: str,
    level: str | None,
) -> None:
    coerced = coerce_to_soai_error(exception, operation=operation)
    if level is None:
        log_exception(
            logger,
            coerced,
            message=message,
            operation=operation,
        )
        return
    log_exception(
        logger,
        coerced,
        message=message,
        operation=operation,
        level=level,
    )


def coerce_and_log_unexpected_shutdown_exception_and_return_one(
    logger: LoggerProtocol,
    exception: BaseException,
    *,
    message: str,
    operation: str,
    level: str | None,
) -> int:
    coerce_and_log_unexpected_shutdown_exception(
        logger,
        exception,
        message=message,
        operation=operation,
        level=level,
    )
    return 1
