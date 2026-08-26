"""SoAI - Structured exception logging primitives [backend/core/errors/exception_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.errors.trace_logging import TRACE_LEVEL
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.logging.protocols import ExcInfoType, LogArg
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "log_exception",
    "log_handled_exception",
    "resolve_logger_function_by_level",
)


def resolve_logger_function_by_level(
    logger: LoggerProtocol,
    level: str,
) -> Callable[..., None] | None:
    logger_function: Callable[..., None] | None = None
    if level == "trace":

        def _trace_logger_function(
            message: JSONValue,
            *args: LogArg,
            exc_info: ExcInfoType = None,
            stack_info: bool = False,
            stacklevel: int = 1,
            extra: Mapping[str, JSONValue] | None = None,
        ) -> None:
            logger.log(
                TRACE_LEVEL,
                message,
                *args,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel,
                extra=extra,
            )

        logger_function = _trace_logger_function
        return logger_function
    try:
        if level == "debug":
            logger_function = logger.debug
        elif level == "info":
            logger_function = logger.info
        elif level == "warning":
            logger_function = logger.warning
        elif level == "error":
            logger_function = logger.error
        elif level == "critical":
            logger_function = logger.critical
    except AttributeError:
        return None
    if callable(logger_function):
        return logger_function
    return None


def log_exception(
    logger: LoggerProtocol,
    exception: BaseException,
    *,
    message: str,
    trace_id: str | None = None,
    operation: str | None = None,
    details: Mapping[str, JSONValue] | None = None,
    level: str = "error",
) -> None:
    if isinstance(exception, SoAIError):
        if trace_id is None:
            trace_id = exception.trace_id
        if operation is None:
            operation = exception.operation
        if details is None:
            details = exception.details
    payload: JSONDict = {}
    if trace_id:
        payload["trace_id"] = trace_id
    if operation:
        payload["operation"] = operation
    if details:
        payload["details"] = dict(details)
    exception_to_log: BaseException = exception
    if isinstance(exception, SoAIError):
        payload["code"] = exception.code
        cause_exception = exception.cause
        if cause_exception is not None:
            exception_to_log = cause_exception
    extra = {"soai_error": payload} if payload else None
    resolved_exc_info: ExcInfoType = (
        type(exception_to_log),
        exception_to_log,
        exception_to_log.__traceback__,
    )
    logger_function = resolve_logger_function_by_level(logger, level)
    if callable(logger_function):
        logger_function(message, exc_info=resolved_exc_info, extra=extra)
        return
    logger.error(message, exc_info=resolved_exc_info, extra=extra)


def log_handled_exception(
    logger: LoggerProtocol,
    exception: BaseException,
    *,
    message: str,
    trace_id: str | None = None,
    operation: str | None = None,
    details: Mapping[str, JSONValue] | None = None,
    level: str = "warning",
) -> None:
    if isinstance(exception, SoAIError):
        if trace_id is None:
            trace_id = exception.trace_id
        if operation is None:
            operation = exception.operation
        if details is None:
            details = exception.details
    payload: JSONDict = {
        "error_class": type(exception).__name__,
        "error_message": str(exception),
    }
    if trace_id:
        payload["trace_id"] = trace_id
    if operation:
        payload["operation"] = operation
    if details:
        payload["details"] = dict(details)
    if isinstance(exception, SoAIError):
        payload["code"] = exception.code
        payload["http_status"] = int(exception.http_status)
    extra = {"soai_error": payload} if payload else None
    logger_function = resolve_logger_function_by_level(logger, level)
    if callable(logger_function):
        logger_function(message, extra=extra)
        return
    logger.warning(message, extra=extra)
