"""SoAI - Agent turn lifecycle noncritical logging [backend/features/agent/runtime/turn_lifecycle/noncritical_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception

if TYPE_CHECKING:
    from core.errors.exceptions import SoAIError
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_noncritical_turn_details",
    "log_noncritical_turn_exception",
)


def build_noncritical_turn_details(
    *,
    conv_id: str,
    turn_id: str,
    context_message: str,
    request_id: str | None,
) -> JSONDict:
    details: JSONDict = {
        "conv_id": conv_id,
        "turn_id": turn_id,
        "context_message": context_message,
    }
    if request_id is not None:
        details["request_id"] = request_id
    return details


def log_noncritical_turn_exception(
    *,
    logger: LoggerProtocol,
    exception: SoAIError,
    message: str,
    trace_id: str,
    operation: str,
    details: JSONDict,
) -> None:
    log_handled_exception(
        logger,
        exception,
        message=message,
        trace_id=trace_id,
        operation=operation,
        level="debug",
        details=details,
    )
