"""SoAI - Browser persistent profile path resolution [backend/mcp/tools/browser/profile_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from filelock import BaseFileLock, Timeout

from core.errors.exceptions import ValidationError
from mcp.tools.browser.config_paths import (
    build_hashed_browser_path,
    require_browser_path_under_base,
    resolve_browser_base_dir,
    resolve_lock_path,
)
from mcp.tools.browser.config_values import browser_min_float

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "acquire_file_lock",
    "require_user_data_dir_under_base",
    "resolve_user_data_dir_base_dir",
    "resolve_user_data_dir_lock_path",
    "resolve_user_data_dir_lock_timeout_sec",
    "resolve_user_data_dir_path",
)

BROWSER_USER_DATA_DIR_LAYOUT_VERSION = 1


def resolve_user_data_dir_base_dir(*, config: ConfigProtocol) -> str:
    return resolve_browser_base_dir(
        config,
        "TOOLS.MCP.BROWSER.USER_DATA_DIR_BASE_DIR",
        empty_message="TOOLS.MCP.BROWSER.USER_DATA_DIR_BASE_DIR must be a non-empty string.",
    )


def resolve_user_data_dir_lock_timeout_sec(*, config: ConfigProtocol) -> float:
    value = browser_min_float(
        config,
        "TOOLS.MCP.BROWSER.USER_DATA_DIR_LOCK_TIMEOUT_SEC",
        30.0,
        min_value=1.0,
    )
    return min(600.0, value)


def resolve_user_data_dir_path(
    *,
    config: ConfigProtocol,
    owner_base: str,
    profile: str,
    session_scope: str,
) -> str:
    base_dir = resolve_user_data_dir_base_dir(config=config)
    return build_hashed_browser_path(
        base_dir=base_dir,
        owner_value=owner_base,
        profile=profile,
        session_scope=session_scope,
        filename_suffix=None,
        version_dir=f"v{BROWSER_USER_DATA_DIR_LAYOUT_VERSION}",
    )


def resolve_user_data_dir_lock_path(*, user_data_dir: str) -> str:
    return resolve_lock_path(user_data_dir, label="user_data_dir")


def require_user_data_dir_under_base(
    *,
    config: ConfigProtocol,
    user_data_dir: str,
) -> str:
    base_dir = resolve_user_data_dir_base_dir(config=config)
    return require_browser_path_under_base(
        base_dir=base_dir,
        path=user_data_dir,
        message="Resolved user_data_dir is outside the configured base directory.",
    )


async def acquire_file_lock(
    lock: BaseFileLock,
    *,
    timeout_sec: float,
    poll_interval_sec: float = 0.1,
) -> None:
    value = float(timeout_sec)
    if not value or value < 0.0:
        raise ValidationError("timeout_sec must be a positive number.")
    interval = float(poll_interval_sec)
    if not interval or interval <= 0.0:
        interval = 0.1
    start = time.monotonic()
    while True:
        try:
            lock.acquire(timeout=0)
            return
        except Timeout:
            elapsed = time.monotonic() - start
            if elapsed >= value:
                raise
            await asyncio.sleep(interval)
