"""SoAI - File explorer search cancellation helpers [backend/features/api/routes/file_explorer/search_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from features.api.runtime.request_disconnect import run_with_request_disconnect_watch

if TYPE_CHECKING:
    from fastapi import Request

    from core.files.explorer_models import SearchResult
    from core.files.protocols_explorer import (
        FileExplorerSearchProtocol,
        FileSystemRootScopeProtocol,
    )

__all__ = ("run_file_explorer_directory_search_with_disconnect_watch",)


async def run_file_explorer_directory_search_with_disconnect_watch(
    *,
    request: Request,
    file_explorer_search: FileExplorerSearchProtocol,
    root_scope: FileSystemRootScopeProtocol,
    path: str,
    query: str,
    offset: int,
    limit: int | None,
    case_sensitive: bool,
    include_total: bool,
) -> SearchResult:
    async def run_search(cancellation_event: threading.Event) -> SearchResult:
        return await file_explorer_search.search_directory(
            root_scope,
            path,
            query,
            offset=offset,
            limit=limit,
            case_sensitive=case_sensitive,
            include_total=include_total,
            cancellation_event=cancellation_event,
        )

    return await run_with_request_disconnect_watch(request, run_search)
