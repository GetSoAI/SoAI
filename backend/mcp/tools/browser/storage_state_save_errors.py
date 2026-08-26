"""SoAI - Browser storage_state save error recording [backend/mcp/tools/browser/storage_state_save_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from playwright.async_api import Error

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.logging.protocols import LoggerProtocol
from mcp.tools.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
)
from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "record_driver_closed_save_error",
    "record_playwright_save_error",
    "record_recoverable_save_error",
    "record_validation_save_error",
)

OPERATION = "mcp.browser.storage_state.save_storage_state"


def record_driver_closed_save_error(
    logger: LoggerProtocol,
    state: BrowserSessionState,
    exception: PlaywrightDriverConnectionClosedError,
    *,
    reason: str,
    path: str,
) -> bool:
    log_handled_exception(
        logger,
        exception,
        message="Failed to save browser storageState because the Playwright driver connection was already closed (non-critical).",
        operation=OPERATION,
        details={"reason": str(reason or "").strip(), "path": path},
        level="debug",
    )
    state.storage_state_last_error = str(exception)
    return False


def record_playwright_save_error(
    logger: LoggerProtocol,
    state: BrowserSessionState,
    exception: Error,
    *,
    reason: str,
    path: str,
) -> bool:
    coerced = coerce_to_soai_error(
        exception,
        operation="mcp.browser.storage_state.save_storage_state.playwright",
    )
    log_handled_exception(
        logger,
        coerced,
        message="Failed to save browser storageState (non-critical).",
        operation=OPERATION,
        details={"reason": str(reason or "").strip(), "path": path},
        level="debug",
    )
    state.storage_state_last_error = str(coerced)
    return False


def record_validation_save_error(
    logger: LoggerProtocol,
    state: BrowserSessionState,
    exception: ValidationError,
    *,
    reason: str,
    path: str,
) -> bool:
    log_handled_exception(
        logger,
        exception,
        message="Failed to save browser storageState due to validation error (non-critical).",
        operation=OPERATION,
        details={"reason": str(reason or "").strip(), "path": path},
        level="debug",
    )
    state.storage_state_last_error = str(exception)
    return False


def record_recoverable_save_error(
    logger: LoggerProtocol,
    state: BrowserSessionState,
    exception: SoAIError,
    *,
    reason: str,
    path: str,
) -> bool:
    log_handled_exception(
        logger,
        exception,
        message="Failed to save browser storageState (non-critical).",
        operation=OPERATION,
        details={"reason": str(reason or "").strip(), "path": path},
        level="debug",
    )
    state.storage_state_last_error = str(exception)
    return False
