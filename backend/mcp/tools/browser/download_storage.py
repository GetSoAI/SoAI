"""SoAI - Browser download storage paths and disk policy [backend/mcp/tools/browser/download_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.path_policy import ensure_path_within_base
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from mcp.tools.browser.internal_protocols import (
        BrowserWorkspaceRuntimeSessionsProtocol,
    )
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "BrowserDownloadPaths",
    "ensure_download_paths",
    "prepare_browser_download_paths",
    "sync_download_paths",
)


@dataclass(frozen=True, slots=True)
class BrowserDownloadPaths:
    downloads_dir: str


def _ensure_directory(path: str, *, description: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exception:
        raise MCPToolError(-32603, f"Failed to create {description}: {path}") from exception


def _require_safe_workspace_path(workspace_path: str, candidate: str, *, description: str) -> str:
    try:
        return ensure_path_within_base(
            workspace_path,
            candidate,
            description=description,
            error_cls=ValidationError,
        )
    except ValidationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception


def _build_download_paths(workspace_path: str) -> BrowserDownloadPaths:
    downloads_dir = _require_safe_workspace_path(
        workspace_path,
        os.path.join(workspace_path, "Downloads"),
        description="browser downloads directory",
    )
    return BrowserDownloadPaths(downloads_dir=downloads_dir)


def prepare_browser_download_paths(
    runtime_sessions: BrowserWorkspaceRuntimeSessionsProtocol,
    *,
    owner_key: str,
) -> BrowserDownloadPaths:
    workspace_path = runtime_sessions.require_workspace_path(owner_key)
    paths = _build_download_paths(workspace_path)
    _ensure_directory(paths.downloads_dir, description="browser downloads directory")
    return paths


def ensure_download_paths(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
) -> BrowserDownloadPaths:
    if state.downloads_dir:
        paths = BrowserDownloadPaths(
            downloads_dir=state.downloads_dir,
        )
    else:
        paths = prepare_browser_download_paths(
            utility_tools.runtime_sessions,
            owner_key=state.owner_key,
        )
        state.downloads_dir = paths.downloads_dir
    return paths


async def sync_download_paths(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
) -> BrowserDownloadPaths:
    paths = ensure_download_paths(utility_tools, state)
    await sync_session_state(
        utility_tools.config,
        state,
        downloads_dir=paths.downloads_dir,
    )
    return paths
