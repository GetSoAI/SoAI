"""SoAI - Browser persistence reset tool [backend/mcp/tools/browser/tool_persistence_reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import shutil
from typing import TYPE_CHECKING

from filelock import FileLock, Timeout

from core.errors.exceptions import ValidationError
from core.files.locking import async_guarded_file_lock
from core.files.operations import async_remove
from core.filesystem.async_queries import async_makedirs
from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.browser.profile_config import resolve_profile_config
from mcp.tools.browser.profile_persistence import (
    acquire_file_lock,
    require_user_data_dir_under_base,
    resolve_user_data_dir_lock_path,
    resolve_user_data_dir_lock_timeout_sec,
    resolve_user_data_dir_path,
)
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    build_browser_owner_key,
    parse_browser_profile,
    parse_browser_session_scope,
    require_browser_enabled,
    resolve_browser_owner_base,
)
from mcp.tools.browser.storage_state_paths import (
    resolve_storage_state_lock_path,
    resolve_storage_state_lock_timeout_sec,
    resolve_storage_state_path,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_persistence_reset",)


def _require_confirm(arguments: JSONDict) -> None:
    if arguments.get("confirm") is not True:
        raise MCPToolError(
            -32602,
            "This tool is destructive. Pass confirm=true to proceed.",
        )


async def _delete_user_data_dir(
    *,
    user_data_dir: str,
    lock_path: str,
    lock_timeout_sec: float,
) -> bool:
    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        await async_makedirs(lock_dir, exist_ok=True)
    lock = FileLock(lock_path, timeout=0, thread_local=False)
    try:
        await acquire_file_lock(lock, timeout_sec=lock_timeout_sec)
    except Timeout as exception:
        raise MCPToolError(
            -32603,
            (
                "Timed out waiting for browser profile lock. Another session may still "
                "be using this profile."
            ),
        ) from exception
    deleted = False
    try:
        if await asyncio.to_thread(os.path.isdir, user_data_dir):
            await asyncio.to_thread(shutil.rmtree, user_data_dir)
            deleted = True
    except (OSError, ValidationError) as exception:
        raise MCPToolError(
            -32603,
            f"Failed to delete user data directory: {exception}",
        ) from exception
    finally:
        await asyncio.shield(asyncio.to_thread(lock.release))
    return deleted


async def _delete_storage_state(
    *,
    path: str,
    lock_path: str,
    lock_timeout_sec: float,
) -> bool:
    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        await async_makedirs(lock_dir, exist_ok=True)
    deleted = False
    try:
        async with async_guarded_file_lock(
            lock_path,
            timeout=lock_timeout_sec,
            on_timeout=ValidationError("Timed out waiting for storage_state file lock."),
        ):
            if await asyncio.to_thread(os.path.isfile, path):
                try:
                    await async_remove(path)
                    deleted = True
                except OSError as exception:
                    raise MCPToolError(
                        -32603,
                        f"Failed to delete storage_state file: {exception}",
                    ) from exception
    except ValidationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
    return deleted


async def tool_browser_persistence_reset(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"confirm", *BROWSER_SESSION_PARAM_KEYS}),
        tool_name="browser_persistence_reset",
    )
    require_browser_enabled(utility_tools)
    _require_confirm(arguments)
    profile = parse_browser_profile(arguments, config=utility_tools.config)
    session_scope = parse_browser_session_scope(arguments, config=utility_tools.config)
    profile_config = resolve_profile_config(utility_tools.config, profile=profile)
    persistence_mode = profile_config.persistence
    owner_base = resolve_browser_owner_base(utility_tools, session_scope=session_scope)
    owner_key = build_browser_owner_key(
        owner_base=owner_base,
        profile=profile,
        session_scope=session_scope,
    )
    if persistence_mode == "user_data_dir":
        user_data_dir = resolve_user_data_dir_path(
            config=utility_tools.config,
            owner_base=owner_base,
            profile=profile,
            session_scope=session_scope,
        )
        user_data_dir = require_user_data_dir_under_base(
            config=utility_tools.config,
            user_data_dir=user_data_dir,
        )
        lock_path = resolve_user_data_dir_lock_path(user_data_dir=user_data_dir)
        lock_timeout_sec = resolve_user_data_dir_lock_timeout_sec(config=utility_tools.config)
        await utility_tools.browser_sessions.close_owner_session(owner_key, persist=False)
        deleted = await _delete_user_data_dir(
            user_data_dir=user_data_dir,
            lock_path=lock_path,
            lock_timeout_sec=lock_timeout_sec,
        )
    else:
        path = resolve_storage_state_path(
            config=utility_tools.config,
            owner_key=owner_key,
            profile=profile,
            session_scope=session_scope,
        )
        lock_path = resolve_storage_state_lock_path(path=path)
        lock_timeout_sec = resolve_storage_state_lock_timeout_sec(config=utility_tools.config)
        await utility_tools.browser_sessions.close_owner_session(owner_key, persist=False)
        deleted = await _delete_storage_state(
            path=path,
            lock_path=lock_path,
            lock_timeout_sec=lock_timeout_sec,
        )
    return {
        "reset": True,
        "deleted": deleted,
        "persistence_mode": persistence_mode,
        "profile": profile,
        "session_scope": session_scope,
    }
