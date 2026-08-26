"""SoAI - Browser session context opening [backend/mcp/tools/browser/session_context_open.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from filelock import BaseFileLock, FileLock, Timeout
from playwright.async_api import BrowserContext, Error, HttpCredentials

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.logging.trace import get_logger
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
        await asyncio.to_thread(os.makedirs, lock_dir, exist_ok=True)
    await asyncio.to_thread(os.makedirs, user_data_dir, exist_ok=True)
    profile_lock = FileLock(lock_path, timeout=0, thread_local=False)
    result_profile_lock: BaseFileLock | None = profile_lock
    try:
        await acquire_file_lock(profile_lock, timeout_sec=lock_timeout_sec)
    except Timeout as exception:
        raise SoAITimeoutError(
            "Timed out waiting for browser profile lock. Another session may still be using this profile.",
        ) from exception
    try:
        context_options = resolve_browser_context_options(self.config, profile=profile)
        context = await self.runtime.launch_persistent_context(
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
    except asyncio.CancelledError:
        try:
            await asyncio.shield(asyncio.to_thread(profile_lock.release))
        finally:
            result_profile_lock = None
        raise
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
        try:
            await asyncio.shield(asyncio.to_thread(profile_lock.release))
        finally:
            result_profile_lock = None
        raise
    return BrowserContextOpenResult(
        context=context,
        profile_lock=result_profile_lock,
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
            await asyncio.to_thread(os.makedirs, lock_dir, exist_ok=True)
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
        storage_state_path=storage_state_path,
        storage_state_error=storage_state_error,
        http_credentials=http_credentials,
        ignore_https_errors=bool(ignore_https_errors),
    )
