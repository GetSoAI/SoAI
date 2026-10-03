"""SoAI - Browser session context opening [backend/mcp/tools/browser/session_context_open.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from filelock import BaseFileLock, FileLock, Timeout
from playwright.async_api import Browser, BrowserContext, Error, HttpCredentials

from core.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
    classify_playwright_driver_connection_closed_exception,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.filesystem.path_coercion import normalize_filesystem_path
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC
from mcp.tools.browser.context_options import resolve_browser_context_options
from mcp.tools.browser.profile_persistence import (
    acquire_file_lock,
    require_user_data_dir_under_base,
    resolve_user_data_dir_lock_path,
    resolve_user_data_dir_lock_timeout_sec,
    resolve_user_data_dir_path,
)
from mcp.tools.browser.storage_state_paths import (
    resolve_storage_state_lock_path,
    resolve_storage_state_lock_timeout_sec,
    resolve_storage_state_path,
)

if TYPE_CHECKING:
    from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol

__all__ = (
    "BrowserContextOpenResult",
    "open_storage_state_context",
    "open_user_data_dir_context",
)

LOGGER_NAME = "SoAI.mcp.tools.session_context_open"
OPERATION_CONTEXT_INIT = "mcp.browser.session_context_open.init_context"
OPERATION_NEW_CONTEXT = "mcp.browser.session_context_open.new_context"
_BROWSER_SERVICE_WORKERS_POLICY: Literal["block"] = "block"


@dataclass(frozen=True, slots=True)
class BrowserContextOpenResult:
    context: BrowserContext
    driver_generation: int
    profile_lock: BaseFileLock | None = None
    user_data_dir: str | None = None
    storage_state_path: str | None = None
    storage_state_error: str | None = None
    http_credentials: HttpCredentials | None = None
    ignore_https_errors: bool = False


async def open_user_data_dir_context(
    self: BrowserSessionStoreProtocol,
    *,
    owner_base: str,
    profile: str,
    session_scope: str,
    http_credentials: HttpCredentials | None = None,
    ignore_https_errors: bool = False,
) -> BrowserContextOpenResult:
    user_data_dir = resolve_user_data_dir_path(
        config=self.config,
        owner_base=owner_base,
        profile=profile,
        session_scope=session_scope,
    )
    user_data_dir = require_user_data_dir_under_base(
        config=self.config,
        user_data_dir=user_data_dir,
    )
    lock_path = resolve_user_data_dir_lock_path(user_data_dir=user_data_dir)
    lock_timeout_sec = resolve_user_data_dir_lock_timeout_sec(config=self.config)
    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        await asyncio.to_thread(os.makedirs, normalize_filesystem_path(lock_dir), exist_ok=True)
    await asyncio.to_thread(os.makedirs, normalize_filesystem_path(user_data_dir), exist_ok=True)
    profile_lock = FileLock(normalize_filesystem_path(lock_path), timeout=0, thread_local=False)
    try:
        await acquire_file_lock(profile_lock, timeout_sec=lock_timeout_sec)
    except Timeout as exception:
        raise SoAITimeoutError(
            "Timed out waiting for browser profile lock. Another session may still be using this profile.",
        ) from exception
    context: BrowserContext
    launched = False
    try:
        context_options = resolve_browser_context_options(self.config, profile=profile)
        context, driver_generation = await self.runtime.launch_persistent_context(
            profile=profile,
            user_data_dir=user_data_dir,
            http_credentials=http_credentials,
            ignore_https_errors=bool(ignore_https_errors),
            locale=context_options.locale,
            timezone_id=context_options.timezone_id,
            extra_http_headers=context_options.extra_http_headers,
            viewport=context_options.viewport,
            device_scale_factor=context_options.device_scale_factor,
        )
        launched = True
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(exception, operation=OPERATION_CONTEXT_INIT)
        log_exception(
            logger,
            coerced,
            message="Failed to launch persistent browser context.",
            operation=OPERATION_CONTEXT_INIT,
            details={"user_data_dir": user_data_dir, "profile": profile},
            level="warning",
        )
        raise
    finally:
        if not launched:
            await uncancel_then_cleanup(
                asyncio.wait_for(
                    asyncio.to_thread(profile_lock.release),
                    timeout=CONTROL_TIMEOUT_SEC,
                ),
            )
    return BrowserContextOpenResult(
        context=context,
        driver_generation=driver_generation,
        profile_lock=profile_lock,
        user_data_dir=user_data_dir,
        http_credentials=http_credentials,
        ignore_https_errors=bool(ignore_https_errors),
    )


async def open_storage_state_context(
    self: BrowserSessionStoreProtocol,
    *,
    owner_key: str,
    profile: str,
    session_scope: str,
    http_credentials: HttpCredentials | None = None,
    ignore_https_errors: bool = False,
) -> BrowserContextOpenResult:
    browser = await self.runtime.ensure_browser(profile=profile)
    driver_generation = await self.runtime.generation_for_browser(browser)
    try:
        return await _open_storage_state_context(
            self,
            browser=browser,
            driver_generation=driver_generation,
            owner_key=owner_key,
            profile=profile,
            session_scope=session_scope,
            http_credentials=http_credentials,
            ignore_https_errors=ignore_https_errors,
        )
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except Exception as exception:
        driver_error = classify_playwright_driver_connection_closed_exception(
            exception,
            operation=OPERATION_NEW_CONTEXT,
            details={"profile": profile},
        )
        if driver_error is None:
            raise
        log_exception(
            get_logger(LOGGER_NAME),
            coerce_to_soai_error(driver_error, operation=OPERATION_NEW_CONTEXT),
            message="Browser context creation lost the Playwright driver connection.",
            operation=OPERATION_NEW_CONTEXT,
            details={"profile": profile},
            level="warning",
        )
        await self.runtime.handle_driver_disconnect(driver_generation, driver_error)
        if driver_error is exception:
            raise
        raise driver_error from exception


async def _open_storage_state_context(
    self: BrowserSessionStoreProtocol,
    *,
    browser: Browser,
    driver_generation: int,
    owner_key: str,
    profile: str,
    session_scope: str,
    http_credentials: HttpCredentials | None,
    ignore_https_errors: bool,
) -> BrowserContextOpenResult:
    context_options = resolve_browser_context_options(self.config, profile=profile)
    storage_state_path: str | None = None
    storage_state_error: str | None = None
    if bool(self.config.get_bool("TOOLS.MCP.BROWSER.STORAGE_STATE_ENABLED")):
        storage_state_path = resolve_storage_state_path(
            config=self.config,
            owner_key=owner_key,
            profile=profile,
            session_scope=session_scope,
        )
    storage_state_lock_path = None
    storage_state_lock_timeout_sec = resolve_storage_state_lock_timeout_sec(config=self.config)
    if storage_state_path:
        storage_state_lock_path = resolve_storage_state_lock_path(path=storage_state_path)
        lock_dir = os.path.dirname(storage_state_lock_path)
        if lock_dir:
            await asyncio.to_thread(os.makedirs, normalize_filesystem_path(lock_dir), exist_ok=True)
    if storage_state_path and storage_state_lock_path is not None:
        failure_message = (
            "Failed to load browser storage_state. Run "
            "browser_persistence_reset(confirm=true) for this profile/session_scope "
            "to delete the corrupted state."
        )
        async with async_guarded_file_lock(
            storage_state_lock_path,
            timeout=storage_state_lock_timeout_sec,
            on_timeout=SoAITimeoutError("Timed out waiting for storage_state file lock."),
        ):
            try:
                if not await asyncio.to_thread(os.path.isfile, storage_state_path):
                    context = await browser.new_context(
                        accept_downloads=True,
                        service_workers=_BROWSER_SERVICE_WORKERS_POLICY,
                        http_credentials=http_credentials,
                        ignore_https_errors=bool(ignore_https_errors),
                        locale=context_options.locale,
                        timezone_id=context_options.timezone_id,
                        extra_http_headers=context_options.extra_http_headers,
                        viewport=context_options.viewport,
                        device_scale_factor=context_options.device_scale_factor,
                    )
                else:
                    context = await browser.new_context(
                        storage_state=storage_state_path,
                        accept_downloads=True,
                        service_workers=_BROWSER_SERVICE_WORKERS_POLICY,
                        http_credentials=http_credentials,
                        ignore_https_errors=bool(ignore_https_errors),
                        locale=context_options.locale,
                        timezone_id=context_options.timezone_id,
                        extra_http_headers=context_options.extra_http_headers,
                        viewport=context_options.viewport,
                        device_scale_factor=context_options.device_scale_factor,
                    )
            except Error as exception:
                driver_error = classify_playwright_driver_connection_closed_exception(
                    exception,
                    operation=OPERATION_NEW_CONTEXT,
                    details={"profile": profile},
                )
                if driver_error is not None:
                    raise driver_error from exception
                logger = get_logger(LOGGER_NAME)
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_NEW_CONTEXT,
                )
                log_exception(
                    logger,
                    coerced,
                    message="Failed to load storageState for browser context.",
                    operation=OPERATION_NEW_CONTEXT,
                    details={"storage_state_path": storage_state_path},
                    level="warning",
                )
                storage_state_error = str(coerced)
                raise ValidationError(failure_message) from exception
            except RECOVERABLE_EXCEPTIONS as exception:
                if isinstance(exception, PlaywrightDriverConnectionClosedError):
                    raise
                logger = get_logger(LOGGER_NAME)
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_NEW_CONTEXT,
                )
                log_exception(
                    logger,
                    coerced,
                    message="Failed to load storageState for browser context.",
                    operation=OPERATION_NEW_CONTEXT,
                    details={"storage_state_path": storage_state_path},
                    level="warning",
                )
                storage_state_error = str(coerced)
                raise ValidationError(failure_message) from exception
            return BrowserContextOpenResult(
                context=context,
                driver_generation=driver_generation,
                storage_state_path=storage_state_path,
                storage_state_error=storage_state_error,
                http_credentials=http_credentials,
                ignore_https_errors=bool(ignore_https_errors),
            )
    context = await browser.new_context(
        accept_downloads=True,
        service_workers=_BROWSER_SERVICE_WORKERS_POLICY,
        http_credentials=http_credentials,
        ignore_https_errors=bool(ignore_https_errors),
        locale=context_options.locale,
        timezone_id=context_options.timezone_id,
        extra_http_headers=context_options.extra_http_headers,
        viewport=context_options.viewport,
        device_scale_factor=context_options.device_scale_factor,
    )
    return BrowserContextOpenResult(
        context=context,
        driver_generation=driver_generation,
        storage_state_path=storage_state_path,
        storage_state_error=storage_state_error,
        http_credentials=http_credentials,
        ignore_https_errors=bool(ignore_https_errors),
    )
