"""SoAI - Browser session store creation [backend/mcp/tools/browser/session_store_create.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from playwright.async_api import BrowserContext, Page

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.tools.browser.download_storage import prepare_browser_download_paths
from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
from mcp.tools.browser.profile_config import resolve_profile_config
from mcp.tools.browser.session_config import (
    apply_page_timeouts,
    attach_context_handlers,
    attach_page_handlers,
)
from mcp.tools.browser.session_context_failure import (
    close_failed_context_initialization,
)
from mcp.tools.browser.session_context_open import (
    open_storage_state_context,
    open_user_data_dir_context,
)
from mcp.tools.browser.session_store_lifecycle import (
    close_browser_context,
    touch_session_state,
)
from mcp.tools.browser.session_sync import (
    install_context_page_tracking,
    sync_session_state,
)
from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "create_tab",
    "get_or_create_session",
)

OPERATION_INIT_CONTEXT = "mcp.browser.session_store_create.get_or_create_session.init_context"
OPERATION_INIT_CONTEXT_CLOSE = (
    "mcp.browser.session_store_create.get_or_create_session.init_context.close_context"
)
LOGGER_NAME = "SoAI.mcp.tools.session_store_create"


async def create_tab(
    self: BrowserSessionStoreProtocol,
    state: BrowserSessionState,
) -> Page:
    page = await state.context.new_page()
    attach_page_handlers(self.config, state, page)
    apply_page_timeouts(self.config, page)
    state.known_page_ids.add(id(page))
    return page


async def get_or_create_session(
    self: BrowserSessionStoreProtocol,
    *,
    owner_key: str,
    owner_base: str,
    profile: str,
    session_scope: str,
) -> BrowserSessionState:
    resolved_owner_key = str(owner_key or "").strip()
    if not resolved_owner_key:
        raise ValidationError("Browser session owner key is required.")
    resolved_owner_base = str(owner_base or "").strip()
    if not resolved_owner_base:
        raise ValidationError("Browser session owner base is required.")

    await self.prune()
    async with self.sessions_lock:
        existing = self.sessions.get(resolved_owner_key)
        if existing is not None:
            if existing.context_closed:
                self.sessions.pop(resolved_owner_key)
            else:
                touch_session_state(existing)
                return existing
        create_lock = self.owner_create_locks.get(resolved_owner_key)
        if create_lock is None:
            create_lock = asyncio.Lock()
            self.owner_create_locks[resolved_owner_key] = create_lock

    async with create_lock:
        await self.prune()
        async with self.sessions_lock:
            existing = self.sessions.get(resolved_owner_key)
            if existing is not None:
                if existing.context_closed:
                    self.sessions.pop(resolved_owner_key)
                else:
                    touch_session_state(existing)
                    return existing

        resolved_profile = str(profile or "").strip()
        if not resolved_profile:
            raise ValidationError("Browser session profile is required.")
        resolved_scope = str(session_scope or "").strip()
        if not resolved_scope:
            raise ValidationError("Browser session scope is required.")
        profile_cfg = resolve_profile_config(
            self.config,
            profile=resolved_profile,
        )
        persistence_mode = str(profile_cfg.persistence or "").strip().lower() or "storage_state"
        if persistence_mode == "user_data_dir" and profile_cfg.cdp_url is not None:
            raise ValidationError(
                f"TOOLS.MCP.BROWSER.PROFILES.{profile_cfg.name}.persistence=user_data_dir is not supported for remote CDP profiles.",
            )

        storage_state_path: str | None = None
        storage_state_error: str | None = None
        context: BrowserContext
        profile_lock = None
        user_data_dir: str | None = None
        download_paths = prepare_browser_download_paths(
            self.runtime_sessions,
            owner_key=resolved_owner_key,
        )

        if persistence_mode == "user_data_dir":
            context_result = await open_user_data_dir_context(
                self,
                owner_base=resolved_owner_base,
                profile=resolved_profile,
                session_scope=resolved_scope,
            )
        else:
            context_result = await open_storage_state_context(
                self,
                owner_key=resolved_owner_key,
                profile=resolved_profile,
                session_scope=resolved_scope,
            )
        context = context_result.context
        profile_lock = context_result.profile_lock
        user_data_dir = context_result.user_data_dir
        storage_state_path = context_result.storage_state_path
        storage_state_error = context_result.storage_state_error

        state = BrowserSessionState(
            owner_key=resolved_owner_key,
            owner_base=resolved_owner_base,
            context=context,
            http_credentials=context_result.http_credentials,
            ignore_https_errors=bool(context_result.ignore_https_errors),
            runtime_flags=self.runtime_flags,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            persistence_mode=persistence_mode,
            user_data_dir=user_data_dir,
            profile_lock=profile_lock,
            storage_manager=self.storage_manager,
            profile=resolved_profile,
            session_scope=resolved_scope,
            storage_state_path=storage_state_path,
            storage_state_last_error=storage_state_error,
            downloads_dir=download_paths.downloads_dir,
            adblock_service=self.adblock_service,
        )
        try:
            install_context_page_tracking(self.config, state)
            await attach_context_handlers(self.config, state)
            await sync_session_state(
                self.config,
                state,
                enforce_page_limit=True,
            )
        except asyncio.CancelledError:
            await asyncio.shield(
                close_browser_context(
                    state,
                    OPERATION_INIT_CONTEXT_CLOSE,
                ),
            )
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_INIT_CONTEXT,
            )
            log_exception(
                logger,
                coerced,
                message="Failed to initialize browser context.",
                operation=OPERATION_INIT_CONTEXT,
                details={
                    "owner_key": resolved_owner_key,
                    "profile": resolved_profile,
                },
                level="warning",
            )
            await close_failed_context_initialization(
                state,
                operation=OPERATION_INIT_CONTEXT,
            )
            raise

        async with self.sessions_lock:
            self.sessions[resolved_owner_key] = state
            touch_session_state(state)

    await self.prune()
    return state
