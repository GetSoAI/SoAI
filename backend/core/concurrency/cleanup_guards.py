"""SoAI - Non-raising cleanup execution helpers [backend/core/concurrency/cleanup_guards.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("cleanup_no_raise",)

OPERATION_CORE_CONCURRENCY_CLEANUP_GUARDS_CLEANUP_NO_RAISE = (
    "core.concurrency.cleanup_guards.cleanup_no_raise"
)


async def cleanup_no_raise[T](
    cleanup_operation: Awaitable[T],
    *,
    logger: LoggerProtocol,
    message: str,
    operation: str,
    details: Mapping[str, JSONValue] | None = None,
    level: str = "debug",
) -> T | None:
    try:
        return await cleanup_operation
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(
            exception,
            operation=operation,
            details=details,
        )
        log_exception(
            logger,
            error,
            message=message,
            operation=OPERATION_CORE_CONCURRENCY_CLEANUP_GUARDS_CLEANUP_NO_RAISE,
            details=details,
            level=level,
        )
        return None
