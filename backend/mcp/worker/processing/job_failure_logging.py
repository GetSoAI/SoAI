"""SoAI - MCP worker processing non-critical failure logging [backend/mcp/worker/processing/job_failure_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.logging.protocols import LoggerProtocol
from core.types.json import JSONValue

__all__ = ("log_processing_noncritical_failure",)


def log_processing_noncritical_failure(
    logger: LoggerProtocol,
    exception: Exception,
    *,
    message: str,
    operation: str,
    details: Mapping[str, JSONValue],
) -> None:
    coerced = coerce_to_soai_error(exception, operation=operation)
    log_handled_exception(
        logger,
        coerced,
        message=message,
        operation=operation,
        details=details,
        level="warning",
    )
