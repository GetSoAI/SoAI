"""SoAI - Shared GPU result message utilities [backend/hardware/result_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.hardware.gpu_operation_results import build_gpu_result
from core.logging.trace import TraceLogger

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "append_amd_log_message",
    "append_intel_log_message",
    "append_log_message",
    "append_messages",
    "append_recoverable_exception_message",
    "build_gpu_result_message_lists",
    "ensure_message_list",
)


def ensure_message_list(result: JSONDict, key: str) -> list[str]:
    value = result.get(key)
    if isinstance(value, list):
        coerced = [str(item) for item in value]
        result[key] = coerced
        return coerced
    messages: list[str] = []
    result[key] = messages
    return messages


def build_gpu_result_message_lists() -> tuple[JSONDict, list[str], list[str]]:
    result = build_gpu_result()
    messages = ensure_message_list(result, "messages")
    errors = ensure_message_list(result, "errors")
    return (result, messages, errors)


def append_messages(target: list[str], values: JSONValue) -> None:
    if isinstance(values, list):
        target.extend([str(item) for item in values])


def _append_vendor_log_message(
    messages: list[str],
    logger: TraceLogger | None,
    vendor_id: int,
    message: str,
    log_message: str,
) -> None:
    messages.append(message)
    if logger is not None:
        logger.info(log_message, vendor_id, message)


def append_log_message(
    messages: list[str],
    logger: TraceLogger | None,
    vendor_id: int,
    message: str,
) -> None:
    _append_vendor_log_message(messages, logger, vendor_id, message, "NVIDIA GPU %s %s")


def append_amd_log_message(
    messages: list[str],
    logger: TraceLogger | None,
    vendor_id: int,
    message: str,
) -> None:
    _append_vendor_log_message(messages, logger, vendor_id, message, "AMD GPU %s %s")


def append_intel_log_message(
    messages: list[str],
    logger: TraceLogger | None,
    vendor_id: int,
    message: str,
) -> None:
    _append_vendor_log_message(messages, logger, vendor_id, message, "Intel GPU %s %s")


def append_recoverable_exception_message(
    errors: list[str],
    logger: TraceLogger | None,
    exception: Exception,
    message: str,
    operation: str,
    vendor_id: int,
) -> None:
    if logger is not None:
        log_exception(
            logger,
            exception,
            message=message,
            operation=operation,
            details={"vendor_id": vendor_id},
            level="warning",
        )
    errors.append(message)
