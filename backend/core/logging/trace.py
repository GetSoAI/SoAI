"""SoAI - Trace logger helpers [backend/core/logging/trace.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TypeGuard

from core.errors.exceptions import StateError
from core.errors.trace_logging import SoAILogger, ensure_trace_logging
from core.logging.protocols import TraceContextProtocol, TraceLogger

__all__ = (
    "TraceLogger",
    "get_context_trace_id",
    "get_logger",
)


def _is_trace_logger(logger: logging.Logger) -> TypeGuard[TraceLogger]:
    return isinstance(logger, SoAILogger)


def get_logger(name: str) -> TraceLogger:
    ensure_trace_logging()
    logger = logging.Logger.manager.getLogger(name)
    if not _is_trace_logger(logger):
        raise StateError(
            "Trace logger is not configured. Ensure logging bootstrap registers trace().",
        )
    return logger


def get_context_trace_id(context: TraceContextProtocol | None) -> str | None:
    if context is None:
        return None
    try:
        trace_id = context.trace_id
    except AttributeError:
        trace_id = None
    return trace_id if isinstance(trace_id, str) and trace_id else None
