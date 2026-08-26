"""SoAI - Messaging observability emission policy [backend/core/messaging/observability_emission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.trace_logging import TRACE_LEVEL
from core.messaging.observability_fields import render_messaging_log_fields

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.logging.rate_limited_logger import RateLimitedLogger
    from core.logging.trace import TraceLogger
    from core.messaging.observability_fields import MessagingLogFields

__all__ = (
    "MESSAGING_LOG_LINE",
    "log_messaging_bounded_failure",
    "log_messaging_diagnostic",
    "log_messaging_lifecycle",
    "log_messaging_trace",
)

MESSAGING_LOG_LINE = "%s %s"


def log_messaging_lifecycle(
    logger: LoggerProtocol,
    *,
    message: str,
    log_fields: MessagingLogFields,
) -> None:
    if not logger.isEnabledFor(logging.INFO):
        return
    logger.info(MESSAGING_LOG_LINE, message, render_messaging_log_fields(log_fields))


def log_messaging_diagnostic(
    logger: LoggerProtocol,
    *,
    message: str,
    log_fields: MessagingLogFields,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(MESSAGING_LOG_LINE, message, render_messaging_log_fields(log_fields))


def log_messaging_trace(
    logger: TraceLogger,
    *,
    message: str,
    log_fields: MessagingLogFields,
) -> None:
    if not logger.isEnabledFor(TRACE_LEVEL):
        return
    logger.trace(MESSAGING_LOG_LINE, message, render_messaging_log_fields(log_fields))


def log_messaging_bounded_failure(
    logger: LoggerProtocol,
    limiter: RateLimitedLogger,
    *,
    message: str,
    log_fields: MessagingLogFields,
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    should_emit, suppressed_count = limiter.should_emit()
    if not should_emit:
        return
    logger.debug(
        MESSAGING_LOG_LINE,
        message,
        render_messaging_log_fields(replace(log_fields, suppressed_count=suppressed_count)),
    )
