"""SoAI - Browser storage_state save operation [backend/mcp/tools/browser/storage_state_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Mapping
from io import TextIOBase
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.filesystem.atomic_writes import atomic_write_text
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)
from mcp.tools.browser.config_values import browser_min_float
from mcp.tools.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
    classify_playwright_driver_connection_closed_exception,
)
from mcp.tools.browser.session_state import (
    browser_session_can_use_context,
    mark_browser_session_driver_disconnected,
)
from mcp.tools.browser.storage_state_paths import (
    is_storage_state_enabled,
    maybe_attach_storage_state_path,
    resolve_storage_state_lock_path,
    resolve_storage_state_lock_timeout_sec,
)
from mcp.tools.browser.storage_state_save_errors import (
    record_driver_closed_save_error,
    record_playwright_save_error,
    record_recoverable_save_error,
    record_validation_save_error,
)
from mcp.tools.browser.types import BrowserSessionState

if TYPE_CHECKING:
    from playwright.async_api import StorageState

    from core.config.protocols import ConfigProtocol

__all__ = ("save_storage_state",)

LOGGER_NAME = "SoAI.mcp.tools.storage_state_persistence"
OPERATION = "mcp.browser.storage_state.save_storage_state"
OPERATION_READ = "mcp.browser.storage_state.save_storage_state.read"
_STORAGE_STATE_READ_EXCEPTIONS: tuple[type[Exception], ...] = (
    PlaywrightDriverConnectionClosedError,
    Error,
    *RECOVERABLE_EXCEPTIONS,
)


async def save_storage_state(
    *,
    config: ConfigProtocol,
    state: BrowserSessionState,
    reason: str,
    force: bool,
) -> bool:
    if state.persistence_mode == "user_data_dir":
        return False
    if not is_storage_state_enabled(config=config):
        return False
    try:
        maybe_attach_storage_state_path(config=config, state=state)
    except ValidationError as exception:
        state.storage_state_last_error = str(exception)
        return False
    if state.storage_state_path is None:
        return False
    if not browser_session_can_use_context(state):
        if state.driver_disconnect_reason is not None:
            state.storage_state_last_error = state.driver_disconnect_reason
        return False
    if not force and not state.storage_state_dirty:
        return False
    if _save_is_throttled(config=config, state=state, force=force):
        return False
    return await _write_storage_state(config=config, state=state, reason=reason)


def _save_is_throttled(
    *,
    config: ConfigProtocol,
    state: BrowserSessionState,
    force: bool,
) -> bool:
    throttle_sec = browser_min_float(
        config,
        "TOOLS.MCP.BROWSER.STORAGE_STATE_SAVE_THROTTLE_SEC",
        5.0,
        min_value=0.0,
    )
    now = time.monotonic()
    return (
        not force
        and throttle_sec > 0.0
        and (now - float(state.storage_state_last_saved_monotonic)) < throttle_sec
    )


async def _write_storage_state(
    *,
    config: ConfigProtocol,
    state: BrowserSessionState,
    reason: str,
) -> bool:
    save_timeout_sec = resolve_storage_state_lock_timeout_sec(config=config)
    logger = get_logger(LOGGER_NAME)
    path = str(state.storage_state_path).strip()
    lock_path = resolve_storage_state_lock_path(path=path)
    parent_dir = os.path.dirname(path)
    try:
        if parent_dir:
            await asyncio.to_thread(os.makedirs, parent_dir, exist_ok=True)
        async with async_guarded_file_lock(
            lock_path,
            timeout=save_timeout_sec,
            on_timeout=SoAITimeoutError("Timed out waiting for storage_state file lock."),
        ):
            await _write_locked_storage_state(state=state, path=path, reason=reason)
        state.storage_state_dirty = False
        state.storage_state_last_saved_monotonic = time.monotonic()
        state.storage_state_last_error = None
        return True
    except PlaywrightDriverConnectionClosedError as exception:
        return record_driver_closed_save_error(logger, state, exception, reason=reason, path=path)
    except Error as exception:
        return record_playwright_save_error(logger, state, exception, reason=reason, path=path)
    except ValidationError as exception:
        return record_validation_save_error(logger, state, exception, reason=reason, path=path)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="mcp.browser.storage_state.save_storage_state.recoverable",
        )
        log_exception(
            logger,
            coerced,
            message="Failed to save browser storageState (non-critical).",
            operation=OPERATION,
            details={"reason": str(reason or "").strip(), "path": path},
            level="debug",
        )
        return record_recoverable_save_error(logger, state, coerced, reason=reason, path=path)


async def _write_locked_storage_state(
    *,
    state: BrowserSessionState,
    path: str,
    reason: str,
) -> None:
    payload = await _read_storage_state_payload(state=state)
    raw_json = serialize_json_compact_stable_strict(normalize_for_json(payload), ensure_ascii=False)
    required_bytes = len(raw_json.encode("utf-8"))

    def _writer(handle: TextIOBase) -> None:
        handle.write(raw_json)

    with (
        state.storage_manager.reserve_disk_space(
            path=path,
            required_bytes=required_bytes,
            operation=OPERATION,
            details={
                "reason": str(reason or "").strip(),
                "required_bytes": required_bytes,
            },
        ) as reservation,
        claim_reserved_write(reservation, size_bytes=required_bytes),
    ):
        await asyncio.to_thread(atomic_write_text, path, _writer, fsync=True)


async def _read_storage_state_payload(*, state: BrowserSessionState) -> StorageState:
    details = {
        "owner_key": state.owner_key,
        "profile": state.profile,
        "session_scope": state.session_scope,
    }
    try:
        payload = await state.context.storage_state()
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except _STORAGE_STATE_READ_EXCEPTIONS as exception:
        driver_error = classify_playwright_driver_connection_closed_exception(
            exception,
            operation=OPERATION_READ,
            details=details,
        )
        if driver_error is None:
            raise
        mark_browser_session_driver_disconnected(
            state,
            reason=str(driver_error),
        )
        raise driver_error from exception
    except Exception as exception:
        driver_error = classify_playwright_driver_connection_closed_exception(
            exception,
            operation=OPERATION_READ,
            details=details,
        )
        if driver_error is None:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_READ,
                details=details,
            )
            log_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Failed to read browser storageState payload (non-critical).",
                operation=OPERATION_READ,
                details=details,
                level="debug",
            )
            raise coerced from exception
        mark_browser_session_driver_disconnected(
            state,
            reason=str(driver_error),
        )
        raise driver_error from exception
    if not isinstance(payload, Mapping):
        raise ValidationError("Playwright storage_state() returned an invalid payload.")
    return payload
