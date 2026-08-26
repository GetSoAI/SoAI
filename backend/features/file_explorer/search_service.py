"""SoAI - File explorer search service [backend/features/file_explorer/search_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import fnmatch
import os
import stat
import threading
from collections import deque

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import NotFoundError, SecurityError, ValidationError
from core.files.explorer_models import SearchResult, SearchResultEntry
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from features.file_explorer.entry_metadata import build_file_entry_info
from features.file_explorer.path_resolution import canonicalize_virtual_path
from features.file_explorer.search_dependencies import (
    FileExplorerSearchServiceDependencies,
)

__all__ = ("FILE_EXPLORER_SEARCH_RESULT_LIMIT_MAX", "FileExplorerSearchService")

FILE_EXPLORER_SEARCH_RESULT_LIMIT_MAX = 5000


class FileExplorerSearchService:
    __slots__ = (
        "_config",
        "_listing_pagination_limit",
    )

    def __init__(self, deps: FileExplorerSearchServiceDependencies) -> None:
        self._config: ConfigProtocol = deps.config
        self._listing_pagination_limit = 100

    def initialize(self) -> None:
        listing_limit = self._config.get_int("DATA.FILE_EXPLORER.LISTING_PAGINATION_LIMIT")
        if listing_limit <= 0:
            listing_limit = 200
        self._listing_pagination_limit = min(
            int(listing_limit),
            FILE_EXPLORER_SEARCH_RESULT_LIMIT_MAX,
        )

    async def search_directory(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        query: str,
        *,
        offset: int = 0,
        limit: int | None = None,
        case_sensitive: bool = False,
        include_total: bool = False,
        cancellation_event: threading.Event | None = None,
    ) -> SearchResult:
        virtual_path = canonicalize_virtual_path(root_scope, virtual_path)
        raw_limit = limit if limit is not None else self._listing_pagination_limit
        effective_limit = min(max(1, raw_limit), FILE_EXPLORER_SEARCH_RESULT_LIMIT_MAX)
        effective_offset = max(0, offset)
        real_path = root_scope.resolve(virtual_path)
        scanner_cancellation_event = cancellation_event or threading.Event()

        def _sync_search() -> SearchResult:
            match_func = fnmatch.fnmatchcase if case_sensitive else fnmatch.fnmatch
            has_glob = any(char in query for char in ("*", "?", "["))
            raw_pattern = query if case_sensitive else query.lower()
            query_pattern = raw_pattern if has_glob else f"*{raw_pattern}*"
            total = 0
            scanned = 0
            page: list[SearchResultEntry] = []
            start_index = effective_offset
            end_index = start_index + effective_limit
            display_virtual_path = _display_virtual_path_for_error(virtual_path)

            def raise_if_cancelled() -> None:
                if scanner_cancellation_event.is_set():
                    raise TaskCancelledError(
                        "file_explorer_search",
                        "File explorer search was cancelled.",
                    )

            def read_directory_entries(
                directory_path: str,
                *,
                strict: bool,
            ) -> list[os.DirEntry[str]]:
                raise_if_cancelled()
                if strict:
                    if not os.path.exists(directory_path):
                        _raise_search_root_not_found(display_virtual_path)
                    if not os.path.isdir(directory_path):
                        _raise_search_root_not_directory(display_virtual_path)
                try:
                    entries: list[os.DirEntry[str]] = []
                    with os.scandir(directory_path) as iterator:
                        for entry in iterator:
                            raise_if_cancelled()
                            entries.append(entry)
                except FileNotFoundError as exception:
                    if strict:
                        _raise_search_root_not_found(display_virtual_path, cause=exception)
                    return []
                except OSError as exception:
                    if strict:
                        _raise_search_root_not_accessible(display_virtual_path, cause=exception)
                    return []
                entries.sort(key=lambda entry: entry.name)
                return entries

            def append_result(
                entry: os.DirEntry[str],
                entry_stat: os.stat_result,
                is_dir: bool,
                virtual_entry_path: str,
            ) -> None:
                nonlocal total
                match_index = total
                total = match_index + 1
                if start_index <= match_index < end_index:
                    entry_info = build_file_entry_info(entry.name, entry_stat, is_dir)
                    page.append(
                        SearchResultEntry(
                            path=virtual_entry_path,
                            name=entry_info.name,
                            is_directory=entry_info.is_directory,
                            size=entry_info.size,
                            modified_at_ms=entry_info.modified_at_ms,
                            mime_type=entry_info.mime_type,
                            type_id=entry_info.type_id,
                            type_rank=entry_info.type_rank,
                            permissions=entry_info.permissions,
                        ),
                    )

            def scan_tree() -> bool:
                nonlocal scanned
                directory_queue: deque[str] = deque([real_path])
                while directory_queue:
                    raise_if_cancelled()
                    directory_path = directory_queue.popleft()
                    for entry in read_directory_entries(
                        directory_path,
                        strict=directory_path == real_path,
                    ):
                        raise_if_cancelled()
                        scanned += 1
                        try:
                            entry_stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            continue
                        is_dir = stat.S_ISDIR(entry_stat.st_mode)
                        name_to_check = entry.name if case_sensitive else entry.name.lower()
                        if match_func(name_to_check, query_pattern):
                            try:
                                virtual_entry_path = root_scope.to_virtual_path(entry.path)
                            except SecurityError:
                                virtual_entry_path = None
                            if virtual_entry_path is not None:
                                append_result(entry, entry_stat, is_dir, virtual_entry_path)
                        if not include_total and total > end_index:
                            return True
                        if is_dir:
                            directory_queue.append(entry.path)
                return False

            truncated = scan_tree()
            return SearchResult(
                query=query,
                search_root=virtual_path,
                entries=page,
                total=total,
                offset=effective_offset,
                limit=effective_limit,
                truncated=truncated,
                scanned_entries=scanned,
            )

        worker = create_ephemeral_task(
            asyncio.to_thread(_sync_search),
            name="file-explorer-directory-search",
            log_exceptions=False,
        )
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError as cancellation_exception:
            scanner_cancellation_event.set()
            await wait_for_task_completion(worker)
            if not worker.cancelled():
                worker_exception = worker.exception()
                if worker_exception is not None:
                    cancellation_exception.add_note(
                        f"Directory search scanner stopped with: {worker_exception}",
                    )
            raise
        except TaskCancelledError:
            scanner_cancellation_event.set()
            raise


def _display_virtual_path_for_error(virtual_path: str) -> str:
    stripped = virtual_path.rstrip("/")
    if not stripped:
        return "/"
    name = os.path.basename(stripped)
    return name or "/"


def _raise_search_root_not_found(
    display_virtual_path: str,
    *,
    cause: BaseException | None = None,
) -> None:
    if cause is None:
        raise NotFoundError(
            f"Directory not found: '{display_virtual_path}'.",
            operation="file_explorer.search_directory",
        )
    raise NotFoundError(
        f"Directory not found: '{display_virtual_path}'.",
        operation="file_explorer.search_directory",
    ) from cause


def _raise_search_root_not_directory(display_virtual_path: str) -> None:
    raise ValidationError(f"Path is not a directory: '{display_virtual_path}'.")


def _raise_search_root_not_accessible(
    display_virtual_path: str,
    *,
    cause: BaseException | None = None,
) -> None:
    if cause is None:
        raise ValidationError(f"Directory is not accessible: '{display_virtual_path}'.")
    raise ValidationError(f"Directory is not accessible: '{display_virtual_path}'.") from cause
