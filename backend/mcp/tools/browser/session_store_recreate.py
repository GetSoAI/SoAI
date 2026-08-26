"""SoAI - Browser session context recreation [backend/mcp/tools/browser/session_store_recreate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from playwright.async_api import HttpCredentials

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.tools.browser.download_storage import prepare_browser_download_paths
from mcp.tools.browser.download_tasks import cancel_active_download_tasks
from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
from mcp.tools.browser.page_ref_state import reset_active_page_ref_state
from mcp.tools.browser.session_config import attach_context_handlers
from mcp.tools.browser.session_context_failure import (
    close_failed_context_initialization,
)
from mcp.tools.browser.session_context_open import (
    open_storage_state_context,
    open_user_data_dir_context,
)
from mcp.tools.browser.session_state import reset_browser_session_connectivity
from mcp.tools.browser.session_store_lifecycle import (
    close_browser_context,
    touch_session_state,
)
from mcp.tools.browser.session_sync import (
    install_context_page_tracking,
    sync_session_state,
)
from mcp.tools.browser.storage_state_persistence import save_storage_state
from mcp.tools.browser.types import BrowserSessionState

__all__ = ("recreate_context",)

LOGGER_NAME = "SoAI.mcp.tools.session_store_recreate"
OPERATION_RECREATE = "mcp.browser.session_store.recreate_context"


def _reset_context_state(state: BrowserSessionState) -> None:
    state.pages = []
    state.active_index = 0
    state.known_page_ids = set()

    reset_active_page_ref_state(state)
    state.page_ref_states = {}

    state.dialogs = []
    state.dialog_objects = {}
    state.next_dialog_id = 1
    state.dialog_queue = asyncio.Queue(maxsize=200)

    state.console_messages = []
    state.console_last_call_index = 0
    state.console_page_load_index = 0
    state.console_queue = asyncio.Queue(maxsize=2000)

    state.network_requests = []
    state.network_last_call_index = 0
    state.network_page_load_index = 0
    state.network_queue = asyncio.Queue(maxsize=2000)

    state.downloads = []
    state.download_size_hints = []
    state.next_download_id = 1
    state.download_queue = asyncio.Queue(maxsize=200)
    state.download_tasks = {}
    state.download_target_paths = set()

    state.page_open_queue = asyncio.Queue(maxsize=100)
    state.page_close_queue = asyncio.Queue(maxsize=200)

    state.host_block_cache = set()
    reset_browser_session_connectivity(state)


async def recreate_context(
    self: BrowserSessionStoreProtocol,
    *,
    state: BrowserSessionState,
    http_credentials: HttpCredentials | None,
    ignore_https_errors: bool,
) -> None:
    logger = get_logger(LOGGER_NAME)
    await self.prune()
    touch_session_state(state)
    await cancel_active_download_tasks(state, reason="recreate_context")
    if bool(self.config.get_bool("TOOLS.MCP.BROWSER.STORAGE_STATE_ENABLED")):
        await save_storage_state(
            config=self.config,
            state=state,
            reason="recreate_context",
            force=True,
        )
    await close_browser_context(state, operation=OPERATION_RECREATE)

    download_paths = prepare_browser_download_paths(
        self.runtime_sessions,
        owner_key=state.owner_key,
    )
    context_result = None
    if state.persistence_mode == "user_data_dir":
        context_result = await open_user_data_dir_context(
            self,
            owner_base=state.owner_base,
            profile=state.profile,
            session_scope=state.session_scope,
            http_credentials=http_credentials,
            ignore_https_errors=bool(ignore_https_errors),
        )
    else:
        context_result = await open_storage_state_context(
            self,
            owner_key=state.owner_key,
            profile=state.profile,
            session_scope=state.session_scope,
            http_credentials=http_credentials,
            ignore_https_errors=bool(ignore_https_errors),
        )
    state.context = context_result.context
    state.profile_lock = context_result.profile_lock
    state.user_data_dir = context_result.user_data_dir
    state.storage_state_path = context_result.storage_state_path
    state.storage_state_last_error = context_result.storage_state_error
    state.http_credentials = http_credentials
    state.ignore_https_errors = bool(ignore_https_errors)
    state.downloads_dir = download_paths.downloads_dir
    _reset_context_state(state)
    try:
        install_context_page_tracking(self.config, state)
        await attach_context_handlers(self.config, state)
        await sync_session_state(self.config, state, enforce_page_limit=True)
    except asyncio.CancelledError:
        await asyncio.shield(close_browser_context(state, operation=OPERATION_RECREATE))
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_RECREATE,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to recreate browser context.",
            operation=OPERATION_RECREATE,
            details={"owner_key": state.owner_key, "profile": state.profile},
            level="warning",
        )
        await close_failed_context_initialization(
            state,
            operation=OPERATION_RECREATE,
        )
        raise
