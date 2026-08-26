"""SoAI - Shared EasyList adblock service [backend/core/browser_adblock/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.browser_adblock.matcher import EasyListMatcher, EasyListMatchResult
from core.browser_adblock.rules import parse_easylist_rules
from core.browser_adblock.source import (
    EasyListCachePaths,
    EasyListSnapshot,
    compute_next_refresh_unix,
    load_cached_snapshot,
    load_packaged_snapshot,
    resolve_cache_paths,
    write_cached_snapshot,
)
from core.config.byte_sizes import MIB_BYTES
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError, StateError, ValidationError
from core.errors.external_service_exception import ExternalServiceError
from core.logging.protocols import LoggerProtocol
from core.timing.epoch import epoch_seconds_float

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "EasyListAdblockService",
    "EasyListAdblockServiceDependencies",
    "build_easylist_adblock_service_dependencies",
)

MAX_DOWNLOAD_BYTES = 8 * MIB_BYTES
REQUEST_TIMEOUT_SECONDS = 15.0
OPERATION_DOWNLOAD_EASYLIST = "core.browser_adblock.service.download_easylist"
OPERATION_PERSIST_SNAPSHOT = "core.browser_adblock.service.persist_snapshot"
CACHE_PERSISTENCE_EXCEPTIONS: tuple[type[Exception], ...] = (
    InsufficientDiskSpaceError,
    OSError,
    StateError,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class EasyListAdblockServiceDependencies:
    http_client: httpx2.AsyncClient
    list_url: str
    logger: LoggerProtocol
    cache_paths: EasyListCachePaths
    matcher: EasyListMatcher
    snapshot: EasyListSnapshot
    refresh_lock: asyncio.Lock
    storage_manager: StorageManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="EasyListAdblockServiceDependencies",
            cache_paths=self.cache_paths,
            http_client=self.http_client,
            list_url=self.list_url,
            logger=self.logger,
            matcher=self.matcher,
            refresh_lock=self.refresh_lock,
            snapshot=self.snapshot,
            storage_manager=self.storage_manager,
        )


class EasyListAdblockService:
    def __init__(self, deps: EasyListAdblockServiceDependencies) -> None:
        self.http_client = deps.http_client
        self.list_url = deps.list_url
        self.logger = deps.logger
        self.cache_paths = deps.cache_paths
        self._matcher = deps.matcher
        self._snapshot = deps.snapshot
        self._refresh_lock = deps.refresh_lock
        self._storage_manager = deps.storage_manager

    @property
    def next_refresh_unix(self) -> float:
        return self._snapshot.next_refresh_unix

    @property
    def source_name(self) -> str:
        return self._snapshot.source_name

    def match(
        self,
        request_url: str,
        *,
        request_host: str | None,
        request_type: str | None,
        document_host: str | None,
        is_third_party: bool | None,
    ) -> EasyListMatchResult:
        return self._matcher.match(
            request_url,
            request_host=request_host,
            request_type=request_type,
            document_host=document_host,
            is_third_party=is_third_party,
        )

    async def refresh_from_remote(self) -> None:
        if self._snapshot.next_refresh_unix > epoch_seconds_float():
            return
        async with self._refresh_lock:
            if self._snapshot.next_refresh_unix > epoch_seconds_float():
                return
            raw_text = await _download_easylist(self.http_client, self.list_url)
            compiled_matcher = _compile_matcher(raw_text)
            refreshed_snapshot = self._persist_refreshed_snapshot(raw_text)
            self._matcher = compiled_matcher
            self._snapshot = refreshed_snapshot

    def _persist_refreshed_snapshot(self, raw_text: str) -> EasyListSnapshot:
        fetched_at_unix = epoch_seconds_float()
        try:
            return write_cached_snapshot(
                self.cache_paths,
                raw_text=raw_text,
                source_name=self.list_url,
                fetched_at_unix=fetched_at_unix,
                storage_manager=self._storage_manager,
            )
        except CACHE_PERSISTENCE_EXCEPTIONS as exception:
            log_handled_exception(
                self.logger,
                exception,
                message="Browser adblock cache could not be written; refreshed rules stay in memory for this run.",
                operation=OPERATION_PERSIST_SNAPSHOT,
                details={"cache_file_path": self.cache_paths.cache_file_path},
                level="warning",
            )
            return EasyListSnapshot(
                raw_text=raw_text,
                source_name=self.list_url,
                fetched_at_unix=fetched_at_unix,
                next_refresh_unix=compute_next_refresh_unix(
                    raw_text,
                    fetched_at_unix=fetched_at_unix,
                ),
            )


def build_easylist_adblock_service_dependencies(
    *,
    config: ConfigProtocol,
    http_client: httpx2.AsyncClient,
    logger: LoggerProtocol,
    storage_manager: StorageManagerProtocol,
) -> EasyListAdblockServiceDependencies:
    cache_paths = resolve_cache_paths(config.require_str("SYSTEM.PATHS.BASE"))
    list_url = config.require_str("TOOLS.MCP.BROWSER.AD_BLOCK_LIST_URL")
    packaged_snapshot = load_packaged_snapshot()
    try:
        cached_snapshot = load_cached_snapshot(cache_paths)
    except (OSError, ValidationError, ValueError) as exception:
        logger.warning(
            "Browser adblock cache load failed; using packaged snapshot: %s",
            str(exception),
        )
        cached_snapshot = None
    active_snapshot = cached_snapshot if cached_snapshot is not None else packaged_snapshot
    matcher = _compile_matcher(active_snapshot.raw_text)
    return EasyListAdblockServiceDependencies(
        http_client=http_client,
        list_url=list_url,
        logger=logger,
        cache_paths=cache_paths,
        matcher=matcher,
        snapshot=active_snapshot,
        refresh_lock=asyncio.Lock(),
        storage_manager=storage_manager,
    )


def _compile_matcher(raw_text: str) -> EasyListMatcher:
    parsed_rules = parse_easylist_rules(raw_text)
    if not parsed_rules:
        raise ValidationError("EasyList parsing produced no supported network rules.")
    return EasyListMatcher(parsed_rules)


async def _download_easylist(client: httpx2.AsyncClient, list_url: str) -> str:
    response_bytes = bytearray()
    try:
        async with client.stream(
            "GET",
            list_url,
            follow_redirects=True,
            timeout=httpx2.Timeout(REQUEST_TIMEOUT_SECONDS),
        ) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length", "").strip()
            if content_length.isdigit() and int(content_length) > MAX_DOWNLOAD_BYTES:
                raise ValidationError(
                    "Configured EasyList download exceeds the maximum allowed size.",
                )
            async for chunk in response.aiter_bytes():
                response_bytes.extend(chunk)
                if len(response_bytes) > MAX_DOWNLOAD_BYTES:
                    raise ValidationError(
                        "Configured EasyList download exceeded the maximum allowed size.",
                    )
    except httpx2.HTTPError as exception:
        raise ExternalServiceError(
            "EasyList download failed.",
            details={"list_url": list_url},
            operation=OPERATION_DOWNLOAD_EASYLIST,
            cause=exception,
        ) from exception
    return bytes(response_bytes).decode("utf-8", errors="replace")
