"""SoAI - Config loading and cache application for reconciliation [backend/app/config/reconciliation_applier.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from app.config.internal_protocols import ConfigCacheProtocol
from app.config.io import ConfigIO
from app.config.reconciliation_failures import record_failed_read
from core.config.changes import (
    compute_core_changed_config_areas,
    compute_top_level_changed_keys,
)
from core.config.locks import ConfigLockTimeout
from core.config.types import KnownFileState, ScanReadFailure
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_system import (
    ConfigReloadedEvent,
    ConfigReloadFailedEvent,
    ConfigRemovedEvent,
)
from core.logging.protocols import LoggerProtocol
from core.serialization.json import normalize_for_json

__all__ = (
    "ConfigApplier",
    "ConfigApplierDependencies",
    "LoadOutcome",
)

OPERATION_CONFIG_MANAGER_APPLY_CONFIG_SNAPSHOT = "config_manager.apply_config_snapshot"
OPERATION_CONFIG_MANAGER_PUBLISH_RELOAD_FAILED = "config_manager.publish_reload_failed"
OPERATION_CONFIG_MANAGER_SCAN_FILESYSTEM_STATE = "config_manager.scan_filesystem_state"


@dataclass(frozen=True, slots=True)
class LoadOutcome:
    success: bool
    raw_contents: str | None
    content_hash: str | None
    error: str | None
    transient_lock: bool


@dataclass(frozen=True, slots=True)
class ConfigApplierDependencies:
    io: ConfigIO
    cache: ConfigCacheProtocol
    event_bus: EventBusProtocol
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigApplierDependencies",
            cache=self.cache,
            event_bus=self.event_bus,
            io=self.io,
            logger=self.logger,
        )


class ConfigApplier:
    def __init__(self, deps: ConfigApplierDependencies) -> None:
        self._deps = deps

    async def try_load_config_snapshot(
        self,
        *,
        path: str,
        config_name: str,
    ) -> LoadOutcome:
        try:
            raw_contents, content_hash = await self._deps.io.read_config_snapshot(
                config_path=path,
                config_name=config_name,
            )
            return LoadOutcome(
                success=True,
                raw_contents=raw_contents,
                content_hash=content_hash,
                error=None,
                transient_lock=False,
            )
        except ConfigLockTimeout as exception:
            return LoadOutcome(
                success=False,
                raw_contents=None,
                content_hash=None,
                error=str(exception),
                transient_lock=True,
            )
        except ConfigurationError as exception:
            return LoadOutcome(
                success=False,
                raw_contents=None,
                content_hash=None,
                error=str(exception),
                transient_lock=False,
            )

    def record_load_failure(
        self,
        scan_read_failures: dict[str, ScanReadFailure],
        *,
        path: str,
        now: float,
        error: str,
        transient_lock: bool,
    ) -> bool:
        return record_failed_read(
            scan_read_failures,
            ScanReadFailure,
            path=path,
            now=now,
            error_signature=error,
            transient_lock=transient_lock,
        )

    async def apply_to_cache_and_publish(
        self,
        *,
        config_name: str,
        config_path: str,
        raw_contents: str,
        stat: os.stat_result,
        content_hash: str | None,
        source: str,
        emit_events: bool,
        revision: int,
    ) -> KnownFileState:
        async with self._deps.cache.lock:
            previous = self._deps.cache.configs.get(config_name)
            previous_payload_raw = normalize_for_json(previous) if previous is not None else None
        data = self._deps.io.parse_config_contents(
            raw_contents,
            config_name=config_name,
            config_path=config_path,
        )
        async with self._deps.cache.lock:
            self._deps.cache.configs[config_name] = data
        new_state = KnownFileState(
            mtime=stat.st_mtime,
            size=stat.st_size,
            content_hash=content_hash,
        )
        if not emit_events:
            return new_state
        payload_value = normalize_for_json(data)
        payload = payload_value if isinstance(payload_value, dict) else {}
        previous_payload = previous_payload_raw if isinstance(previous_payload_raw, dict) else None
        if config_name == "core":
            changed_keys = compute_core_changed_config_areas(
                previous=previous_payload,
                current=payload,
            )
        else:
            changed_keys = compute_top_level_changed_keys(
                previous=previous_payload,
                current=payload,
            )
        try:
            await self._deps.event_bus.publish(
                ConfigReloadedEvent(
                    config_name=config_name,
                    path=config_path,
                    config_dict=payload,
                    content_hash=content_hash,
                    source=source,
                    revision=revision,
                    changed_keys=changed_keys,
                ),
            )
        except RECOVERABLE_EXCEPTIONS as publish_error:
            log_exception(
                self._deps.logger,
                publish_error,
                message="Failed to publish ConfigReloadedEvent",
                operation=OPERATION_CONFIG_MANAGER_APPLY_CONFIG_SNAPSHOT,
                details={"config_name": config_name},
            )
        return new_state

    async def publish_reload_failed(
        self,
        *,
        config_name: str,
        config_path: str,
        error: str,
        content_hash: str | None,
        source: str,
        emit_events: bool,
    ) -> None:
        if not emit_events:
            return
        try:
            await self._deps.event_bus.publish(
                ConfigReloadFailedEvent(
                    config_name=config_name,
                    path=config_path,
                    error=error,
                    content_hash=content_hash,
                    source=source,
                ),
            )
        except RECOVERABLE_EXCEPTIONS as publish_error:
            log_exception(
                self._deps.logger,
                publish_error,
                message="Failed to publish ConfigReloadFailedEvent",
                operation=OPERATION_CONFIG_MANAGER_PUBLISH_RELOAD_FAILED,
                details={"config_name": config_name},
            )

    async def publish_config_removed(
        self,
        *,
        config_name: str,
        config_path: str,
        source: str,
    ) -> None:
        try:
            await self._deps.event_bus.publish(
                ConfigRemovedEvent(config_name=config_name, path=config_path, source=source),
            )
        except RECOVERABLE_EXCEPTIONS as publish_error:
            log_exception(
                self._deps.logger,
                publish_error,
                message="Failed to publish ConfigRemovedEvent",
                operation=OPERATION_CONFIG_MANAGER_SCAN_FILESYSTEM_STATE,
                details={"config_name": config_name},
            )
