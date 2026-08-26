"""SoAI - WebUI conversation absolute-paths resolver schemas and link helpers [backend/features/api/routes/webui/absolute_paths_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, Field

from core.system_api.route_paths import SOAI_FILE_EXPLORER_PREFIX

__all__ = (
    "AbsolutePathsResolveError",
    "AbsolutePathsResolveOk",
    "AbsolutePathsResolveRequest",
    "AbsolutePathsResolveResponse",
    "build_file_explorer_deeplink",
    "build_file_explorer_preview_url",
    "build_file_explorer_read_url",
    "canonicalize_virtual_link_target",
)


class AbsolutePathsResolveRequest(BaseModel):
    paths: list[str] = Field(min_length=1, description="Absolute OS paths to resolve")


class AbsolutePathsResolveError(BaseModel):
    path: str
    status: Literal["error"]
    error_code: str
    error_message: str
    virtual_path: str | None = None
    open_file_explorer_url: str | None = None


class AbsolutePathsResolveOk(BaseModel):
    path: str
    status: Literal["ok"]
    type: Literal["image", "audio", "video", "text", "document", "file", "folder"]
    virtual_path: str
    mime_type: str | None
    size: int
    preview_url: str | None
    download_url: str | None
    open_file_explorer_url: str


class AbsolutePathsResolveResponse(BaseModel):
    results: list[AbsolutePathsResolveOk | AbsolutePathsResolveError]
    override_workspace_path: str | None
    override_is_valid: bool
    override_validation_message: str | None
    effective_workspace_path: str


def canonicalize_virtual_link_target(value: str) -> str:
    trimmed = str(value or "").strip()
    if not trimmed:
        return "/"
    return trimmed if trimmed.startswith("/") else f"/{trimmed}"


def build_file_explorer_deeplink(
    *,
    directory_path: str | None,
    highlight_path: str | None,
    search: str | None,
) -> str:
    query_parts: list[str] = []
    if directory_path is not None:
        canonical_dir = canonicalize_virtual_link_target(directory_path)
        query_parts.append(f"path={quote(canonical_dir, safe='')}")
    if highlight_path is not None:
        canonical_highlight = canonicalize_virtual_link_target(highlight_path)
        query_parts.append(f"highlight={quote(canonical_highlight, safe='')}")
    if search is not None:
        search_value = str(search or "").strip()
        if search_value:
            query_parts.append(f"search={quote(search_value, safe='')}")
    query_string = "&".join(query_parts)
    return f"#fileExplorer?{query_string}" if query_string else "#fileExplorer"


def build_file_explorer_preview_url(path: str, *, download: bool) -> str:
    flag = "1" if download else "0"
    return f"{SOAI_FILE_EXPLORER_PREFIX}/preview?path={quote(path, safe='')}&download={flag}"


def build_file_explorer_read_url(path: str) -> str:
    return f"{SOAI_FILE_EXPLORER_PREFIX}/read?path={quote(path, safe='')}"
