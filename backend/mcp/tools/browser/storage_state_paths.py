"""SoAI - Browser storage_state path resolution [backend/mcp/tools/browser/storage_state_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from mcp.tools.browser.config_paths import (
    build_hashed_browser_path,
    resolve_browser_base_dir,
    resolve_lock_path,
)
from mcp.tools.browser.config_values import browser_min_int
from mcp.tools.browser.types import BrowserSessionState

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "is_storage_state_enabled",
    "maybe_attach_storage_state_path",
    "resolve_existing_storage_state_path",
    "resolve_storage_state_lock_path",
    "resolve_storage_state_lock_timeout_sec",
    "resolve_storage_state_path",
)


def is_storage_state_enabled(*, config: ConfigProtocol) -> bool:
    return bool(config.get_bool("TOOLS.MCP.BROWSER.STORAGE_STATE_ENABLED"))


def _resolve_storage_state_base_dir(*, config: ConfigProtocol) -> str:
    return resolve_browser_base_dir(
        config,
        "TOOLS.MCP.BROWSER.STORAGE_STATE_DIR",
        empty_message="TOOLS.MCP.BROWSER.STORAGE_STATE_DIR must be a non-empty string when enabled.",
    )


def resolve_storage_state_path(
    *,
    config: ConfigProtocol,
    owner_key: str,
    profile: str,
    session_scope: str,
) -> str:
    base_dir = _resolve_storage_state_base_dir(config=config)
    return build_hashed_browser_path(
        base_dir=base_dir,
        owner_value=str(owner_key or ""),
        profile=profile,
        session_scope=session_scope,
        filename_suffix=".json",
    )


def resolve_storage_state_lock_path(*, path: str) -> str:
    return resolve_lock_path(path, label="storage state path")


def resolve_storage_state_lock_timeout_sec(*, config: ConfigProtocol) -> float:
    return float(
        browser_min_int(
            config, "TOOLS.MCP.BROWSER.STORAGE_STATE_SAVE_TIMEOUT_SEC", 10, min_value=1
        ),
    )


def maybe_attach_storage_state_path(
    *,
    config: ConfigProtocol,
    state: BrowserSessionState,
) -> None:
    if state.persistence_mode == "user_data_dir":
        return
    if state.storage_state_path is not None:
        return
    if not is_storage_state_enabled(config=config):
        return
    state.storage_state_path = resolve_storage_state_path(
        config=config,
        owner_key=state.owner_key,
        profile=state.profile,
        session_scope=state.session_scope,
    )


async def resolve_existing_storage_state_path(*, state: BrowserSessionState) -> str | None:
    path = state.storage_state_path
    if not isinstance(path, str) or not path.strip():
        return None
    resolved = path.strip()
    exists = await asyncio.to_thread(os.path.isfile, resolved)
    return resolved if exists else None
