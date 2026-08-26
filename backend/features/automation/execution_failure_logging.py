"""SoAI - Automation execution failure logging policy [backend/features/automation/execution_failure_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("log_automation_run_failure",)


def _resolve_failure_log_level(
    *,
    coerced: SoAIError,
    is_timeout: bool,
    is_cancelled: bool,
) -> str:
    if is_timeout:
        return "error"
    if is_cancelled or int(coerced.http_status) < 500:
        return "warning"
    return "error"


def _is_client_failure(coerced: SoAIError, *, is_timeout: bool, is_cancelled: bool) -> bool:
    return not is_timeout and not is_cancelled and int(coerced.http_status) < 500


def log_automation_run_failure(
    logger: LoggerProtocol,
    coerced: SoAIError,
    *,
    message: str,
    operation: str,
    run_id: str,
    automation_id: str,
    is_timeout: bool,
    is_cancelled: bool,
) -> None:
    details = {"run_id": run_id, "automation_id": automation_id}
    if is_cancelled:
        log_handled_exception(
            logger,
            coerced,
            message=message,
            operation=operation,
            level="info",
            details=details,
        )
        return
    if _is_client_failure(coerced, is_timeout=is_timeout, is_cancelled=is_cancelled):
        log_handled_exception(
            logger,
            coerced,
            message=message,
            operation=operation,
            level="warning",
            details=details,
        )
        return
    log_exception(
        logger,
        coerced,
        message=message,
        operation=operation,
        level=_resolve_failure_log_level(
            coerced=coerced,
            is_timeout=is_timeout,
            is_cancelled=is_cancelled,
        ),
        details=details,
    )
