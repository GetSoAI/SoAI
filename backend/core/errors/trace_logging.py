"""SoAI - Trace logging setup for SoAI loggers [backend/core/errors/trace_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING

from core.logging.log_record import ensure_soai_log_record_factory

if TYPE_CHECKING:
    from core.types.json import JSONValue

    type TraceLogArg = JSONValue
    type TraceExcInfo = bool | tuple[
        type[BaseException],
        BaseException,
        TracebackType | None,
    ] | BaseException | None

__all__ = (
    "SoAILogger",
    "ensure_trace_logging",
)

TRACE_LEVEL = 5


class SoAILogger(logging.Logger):
    def trace(
        self,
        message: str,
        *args: TraceLogArg,
        exc_info: TraceExcInfo = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, JSONValue] | None = None,
    ) -> None:
        if self.isEnabledFor(TRACE_LEVEL):
            self.log(
                TRACE_LEVEL,
                message,
                *args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                stacklevel=stacklevel,
            )


def ensure_trace_logging() -> int:
    logging.addLevelName(TRACE_LEVEL, "TRACE")
    ensure_soai_log_record_factory()
    if not TYPE_CHECKING:
        logging.Logger.trace = SoAILogger.trace
    if logging.getLoggerClass() is not SoAILogger:
        logging.setLoggerClass(SoAILogger)
    return TRACE_LEVEL
