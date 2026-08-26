"""SoAI - Safe callback invocation primitives [backend/core/callbacks/invocation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = ("invoke_callback_safe",)

OPERATION_CORE_CALLBACKS_INVOCATION_INVOKE_CALLBACK_SAFE = (
    "core.callbacks.invocation.invoke_callback_safe"
)


def invoke_callback_safe[T](
    callback: Callable[..., T] | None,
    logger: LoggerProtocol,
    operation: str,
    level: str,
    *args: str | float | bool | bytes | None,
    **callback_fields: str | float | bool | None,
) -> T | None:
    if callback is None:
        return None

    try:
        return callback(*args, **callback_fields)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Callback invocation error",
            operation=OPERATION_CORE_CALLBACKS_INVOCATION_INVOKE_CALLBACK_SAFE,
            details={"operation": operation},
            level=level,
        )
        return None
