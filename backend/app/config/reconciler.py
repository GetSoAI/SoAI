"""SoAI - Configuration filesystem reconciler orchestration [backend/app/config/reconciler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.config.internal_protocols import ConfigCacheProtocol
from app.config.io import ConfigIO
from app.config.reconciliation_applier import ConfigApplier, ConfigApplierDependencies
from app.config.reconciliation_discovery import (
    build_candidate_paths_async,
    filter_paths_to_existing_async,
    list_manageable_configs_async,
)
from app.config.reconciliation_failures import should_retry_failed_read
from core.collections.sets import compute_set_deltas
from core.config.types import KnownFileState, ScanReadFailure
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.logging.protocols import LoggerProtocol

__all__ = (
    "ConfigReconciler",
    "ConfigReconcilerDependencies",
)

OPERATION_CONFIG_MANAGER_LOAD_AND_APPLY_PATH = "config_manager.load_and_apply_path"
OPERATION_CONFIG_MANAGER_SCAN_FILESYSTEM_STATE = "config_manager.scan_filesystem_state"


@dataclass(frozen=True, slots=True)
class ConfigReconcilerDependencies:
    io: ConfigIO
    event_bus: EventBusProtocol
    logger: LoggerProtocol
    cache: ConfigCacheProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigReconcilerDependencies",
            cache=self.cache,
            event_bus=self.event_bus,
            io=self.io,
            logger=self.logger,
        )


class ConfigReconciler:
    def __init__(self, deps: ConfigReconcilerDependencies) -> None:
        self._deps = deps
        self.reconciliation_lock = asyncio.Lock()
        self.known_files_state: dict[str, KnownFileState] = {}
        self.scan_read_failures: dict[str, ScanReadFailure] = {}
        self.file_revisions: dict[str, int] = {}
        self.initial_baseline_established = False
        self._applier = ConfigApplier(
            ConfigApplierDependencies(
                io=deps.io,
                cache=deps.cache,
                event_bus=deps.event_bus,
                logger=deps.logger,
            ),
        )

    def ensure_revision_initialized(self, path: str) -> int:
        existing = self.file_revisions.get(path)
        if isinstance(existing, int) and existing > 0:
            return existing
        self.file_revisions[path] = 1
        return 1

    def bump_revision(self, path: str) -> int:
        next_revision = int(self.file_revisions.get(path, 0)) + 1
        self.file_revisions[path] = next_revision
        return next_revision

    async def list_manageable_configs(self) -> list[str]:
        return await list_manageable_configs_async(
            self._deps.io.plugins_path,
            self._deps.logger,
        )

    async def scan_filesystem_state(
        self,
        *,
        emit_events: bool,
        source: str,
        config_name: str | None,
        delete_from_cache: Callable[[str], Awaitable[None]],
    ) -> None:
        async with self.reconciliation_lock:
            now = asyncio.get_running_loop().time()
            candidate_paths = await build_candidate_paths_async(
                self._deps.io,
                config_name,
                self._deps.logger,
            )
            current_paths_on_disk = await filter_paths_to_existing_async(
                candidate_paths,
                self._deps.logger,
            )
            known_paths = set(self.known_files_state.keys())
            if config_name:
                known_paths = known_paths.intersection(candidate_paths)
            deleted_paths, _ = compute_set_deltas(known_paths, current_paths_on_disk)
            await self._handle_deleted_paths(
                deleted_paths=deleted_paths,
                delete_from_cache=delete_from_cache,
                emit_events=emit_events,
                source=source,
            )
            for path in current_paths_on_disk:
                resolved_name = self._deps.io.path_to_config_name(path)
                if not resolved_name:
                    continue
                await self._process_path_for_changes(
                    path=path,
                    resolved_name=resolved_name,
                    source=source,
                    emit_events=emit_events,
                    now=now,
                )

    async def _handle_deleted_paths(
        self,
        *,
        deleted_paths: set[str],
        delete_from_cache: Callable[[str], Awaitable[None]],
        emit_events: bool,
        source: str,
    ) -> None:
        for path in deleted_paths:
            self.known_files_state.pop(path, None)
            self.file_revisions.pop(path, None)
            self.scan_read_failures.pop(path, None)
            resolved_name = self._deps.io.path_to_config_name(path)
            if resolved_name:
                await delete_from_cache(resolved_name)
                if emit_events:
                    await self._applier.publish_config_removed(
                        config_name=resolved_name,
                        config_path=path,
                        source=source,
                    )

    async def _process_path_for_changes(
        self,
        *,
        path: str,
        resolved_name: str,
        source: str,
        emit_events: bool,
        now: float,
    ) -> None:
        try:
            stat = await asyncio.to_thread(os.stat, path)
        except FileNotFoundError:
            return
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logger,
                exception,
                message="Could not stat file",
                operation=OPERATION_CONFIG_MANAGER_SCAN_FILESYSTEM_STATE,
                details={"path": path},
            )
            return
        previous_state = self.known_files_state.get(path)
        previous_hash = previous_state.content_hash if previous_state else None
        if previous_state is not None and (
            stat.st_mtime == previous_state.mtime
            and stat.st_size == previous_state.size
            and previous_hash is not None
        ):
            return
        if previous_state is not None and (
            stat.st_mtime == previous_state.mtime
            and stat.st_size == previous_state.size
            and not should_retry_failed_read(self.scan_read_failures, path, now=now)
        ):
            return
        await self._load_and_apply_path(
            path=path,
            resolved_name=resolved_name,
            stat=stat,
            source=source,
            emit_events=emit_events,
            now=now,
            previous_hash=previous_hash,
        )

    async def _load_and_apply_path(
        self,
        *,
        path: str,
        resolved_name: str,
        stat: os.stat_result,
        source: str,
        emit_events: bool,
        now: float,
        previous_hash: str | None,
    ) -> None:
        outcome = await self._applier.try_load_config_snapshot(path=path, config_name=resolved_name)
        if not outcome.success:
            self.known_files_state[path] = KnownFileState(
                mtime=stat.st_mtime,
                size=stat.st_size,
                content_hash=None,
            )
            should_publish = self._applier.record_load_failure(
                self.scan_read_failures,
                path=path,
                now=now,
                error=outcome.error or "Unknown error",
                transient_lock=outcome.transient_lock,
            )
            if should_publish and outcome.error:
                log_exception(
                    self._deps.logger,
                    Exception(outcome.error),
                    message="Failed to load configuration",
                    operation=OPERATION_CONFIG_MANAGER_LOAD_AND_APPLY_PATH,
                    details={"config_name": resolved_name, "path": path},
                )
                await self._applier.publish_reload_failed(
                    config_name=resolved_name,
                    config_path=path,
                    error=outcome.error,
                    content_hash=None,
                    source=source,
                    emit_events=emit_events,
                )
            return
        self.scan_read_failures.pop(path, None)
        if previous_hash is not None and outcome.content_hash == previous_hash:
            self.known_files_state[path] = KnownFileState(
                mtime=stat.st_mtime,
                size=stat.st_size,
                content_hash=outcome.content_hash,
            )
            return
        revision = (
            self.bump_revision(path) if emit_events else self.ensure_revision_initialized(path)
        )
        new_state = await self._applier.apply_to_cache_and_publish(
            config_name=resolved_name,
            config_path=path,
            raw_contents=outcome.raw_contents or "",
            stat=stat,
            content_hash=outcome.content_hash,
            source=source,
            emit_events=emit_events,
            revision=revision,
        )
        self.known_files_state[path] = new_state

    async def reconcile_filesystem_state(
        self,
        *,
        update_baseline: bool,
        delete_from_cache: Callable[[str], Awaitable[None]],
    ) -> None:
        source = "baseline" if update_baseline else "reconcile"
        await self.scan_filesystem_state(
            emit_events=not update_baseline,
            source=source,
            config_name=None,
            delete_from_cache=delete_from_cache,
        )
        if update_baseline:
            self.initial_baseline_established = True
            self._deps.logger.info("Configuration baseline has been successfully updated.")
