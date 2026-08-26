"""SoAI - Browser storage_state persistence helpers [backend/mcp/tools/browser/storage_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.storage_state_paths import (
    is_storage_state_enabled,
    maybe_attach_storage_state_path,
    resolve_existing_storage_state_path,
    resolve_storage_state_lock_path,
    resolve_storage_state_lock_timeout_sec,
    resolve_storage_state_path,
)
from mcp.tools.browser.storage_state_persistence import save_storage_state
from mcp.tools.browser.types import BrowserSessionState

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "is_storage_state_enabled",
    "mark_storage_state_dirty",
    "maybe_attach_storage_state_path",
    "maybe_autosave_storage_state",
    "maybe_save_storage_state_for_session",
    "persist_synced_browser_action_storage_state",
    "resolve_existing_storage_state_path",
    "resolve_storage_state_lock_path",
    "resolve_storage_state_lock_timeout_sec",
    "resolve_storage_state_path",
    "save_storage_state",
    "sync_browser_action_state",
)


async def maybe_save_storage_state_for_session(
    *,
    config: ConfigProtocol,
    state: BrowserSessionState,
    reason: str,
    force: bool,
) -> None:
    if not is_storage_state_enabled(config=config):
        return
    async with state.lock:
        await save_storage_state(
            config=config,
            state=state,
            reason=reason,
            force=force,
        )


def mark_storage_state_dirty(state: BrowserSessionState) -> None:
    if state.persistence_mode == "user_data_dir":
        return
    if state.storage_state_path is None:
        return
    state.storage_state_dirty = True


async def maybe_autosave_storage_state(
    *,
    config: ConfigProtocol,
    state: BrowserSessionState,
    reason: str,
) -> bool:
    if state.persistence_mode == "user_data_dir":
        return False
    if not is_storage_state_enabled(config=config):
        return False
    if not bool(config.get_bool("TOOLS.MCP.BROWSER.STORAGE_STATE_AUTOSAVE_ON_MUTATION")):
        return False
    return await save_storage_state(config=config, state=state, reason=reason, force=False)


async def sync_browser_action_state(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    downloads_dir: str,
) -> None:
    await sync_session_state(
        utility_tools.config,
        state,
        downloads_dir=downloads_dir,
    )


async def persist_synced_browser_action_storage_state(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    reason: str,
) -> None:
    mark_storage_state_dirty(state)
    await maybe_autosave_storage_state(
        config=utility_tools.config,
        state=state,
        reason=reason,
    )
