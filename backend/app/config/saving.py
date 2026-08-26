"""SoAI - Config save workflow with event publishing [backend/app/config/saving.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from filelock import Timeout
from ruamel.yaml.comments import CommentedMap

from app.config.internal_protocols import ConfigCacheProtocol, ConfigReconcilerProtocol
from app.config.io import ConfigIO
from app.config.save_disk_io import load_current_config_from_disk, write_config_to_disk
from app.config.save_outcome import ConfigSaveOutcome
from app.config.save_rollback import rollback_after_publish_failure
from core.config.changes import (
    compute_core_changed_config_areas,
    compute_top_level_changed_keys,
)
from core.config.locks import get_lock_path
from core.config.types import KnownFileState
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.events.protocols import EventBusProtocol
from core.events.types_system import ConfigReloadedEvent
from core.files.locking import async_guarded_file_lock
from core.logging.protocols import LoggerProtocol
from core.serialization.json import normalize_for_json
from core.validation.coercion import coerce_json_dict_stringify_non_json_values

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ConfigSaveCoordinator",
    "ConfigSaveCoordinatorDependencies",
)

OPERATION = "config_save_coordinator.update_and_publish"


@dataclass(frozen=True, slots=True)
class ConfigSaveCoordinatorDependencies:
    io: ConfigIO
    reconciler: ConfigReconcilerProtocol
    cache: ConfigCacheProtocol
    event_bus: EventBusProtocol
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigSaveCoordinatorDependencies",
            cache=self.cache,
            event_bus=self.event_bus,
            io=self.io,
            logger=self.logger,
            reconciler=self.reconciler,
        )


class ConfigSaveCoordinator:
    def __init__(self, deps: ConfigSaveCoordinatorDependencies) -> None:
        self._deps = deps

    async def save_and_publish(
        self,
        *,
        config_name: str,
        config_path: str,
        data: ConfigValue,
        source: str,
        changed_keys: frozenset[str] | None = None,
    ) -> bool:
        def updater(_: CommentedMap) -> CommentedMap:
            if data is not None and not isinstance(data, dict | CommentedMap):
                raise ValidationError(
                    f"Invalid config payload type for '{config_name}': {type(data).__name__}",
                )
            if data is None:
                raise ConfigurationError(f"No data to save for config '{config_name}'.")
            if isinstance(data, CommentedMap):
                return copy.deepcopy(data)
            return CommentedMap(copy.deepcopy(data))

        return await self.update_and_publish(
            config_name=config_name,
            config_path=config_path,
            updater=updater,
            source=source,
            changed_keys=changed_keys,
        )

    async def update_and_publish(
        self,
        *,
        config_name: str,
        config_path: str,
        updater: Callable[[CommentedMap], CommentedMap | dict[str, JSONValue]],
        source: str,
        changed_keys: frozenset[str] | None = None,
    ) -> bool:
        await self.save_updated_and_publish(
            config_name=config_name,
            config_path=config_path,
            updater=updater,
            source=source,
            changed_keys=changed_keys,
        )
        return True

    async def save_updated_and_publish(
        self,
        *,
        config_name: str,
        config_path: str,
        updater: Callable[[CommentedMap], CommentedMap | dict[str, JSONValue]],
        source: str,
        changed_keys: frozenset[str] | None,
    ) -> tuple[ConfigSaveOutcome, JSONDict, frozenset[str]]:
        lock_path = get_lock_path(config_path, lock_directory=self._deps.io.lock_directory)

        def _on_timeout(_: Timeout) -> Exception:
            return ConfigurationError(f"Could not acquire lock to save {config_path}.")

        previous_state: KnownFileState | None = None
        previous_cached_snapshot: CommentedMap | None = None
        config_mapping: CommentedMap
        resolved_changed_keys: frozenset[str]
        outcome: ConfigSaveOutcome
        async with async_guarded_file_lock(lock_path, timeout=5, on_timeout=_on_timeout):
            previous_state = self._deps.reconciler.known_files_state.get(config_path)
            current_mapping = await load_current_config_from_disk(
                self._deps.io,
                config_name=config_name,
                config_path=config_path,
            )
            before_plain_raw = (
                normalize_for_json(current_mapping) if current_mapping is not None else None
            )
            before_plain = (
                coerce_json_dict_stringify_non_json_values(before_plain_raw)
                if before_plain_raw is not None
                else None
            )
            async with self._deps.cache.lock:
                cached_snapshot = self._deps.cache.configs.get(config_name)
                previous_cached_snapshot = (
                    copy.deepcopy(cached_snapshot) if cached_snapshot is not None else None
                )
            base_mapping = (
                copy.deepcopy(current_mapping) if current_mapping is not None else CommentedMap()
            )
            updated_mapping = updater(base_mapping)
            if not isinstance(updated_mapping, dict | CommentedMap):
                raise ValidationError(
                    f"Invalid config updater result for '{config_name}': {type(updated_mapping).__name__}",
                )
            if isinstance(updated_mapping, CommentedMap):
                config_mapping = updated_mapping
            else:
                config_mapping = CommentedMap(updated_mapping)
            after_plain_raw = normalize_for_json(config_mapping)
            after_plain = coerce_json_dict_stringify_non_json_values(after_plain_raw)
            if changed_keys is not None:
                resolved_changed_keys = changed_keys
            elif config_name == "core":
                resolved_changed_keys = compute_core_changed_config_areas(
                    previous=before_plain,
                    current=after_plain,
                )
            else:
                resolved_changed_keys = compute_top_level_changed_keys(
                    previous=before_plain,
                    current=after_plain,
                )
            outcome = await write_config_to_disk(
                io=self._deps.io,
                reconciler=self._deps.reconciler,
                cache=self._deps.cache,
                logger=self._deps.logger,
                config_name=config_name,
                config_path=config_path,
                config_mapping=config_mapping,
                previous_cached_snapshot=previous_cached_snapshot,
                lock_path=lock_path,
                previous_state=previous_state,
            )
            reload_event = ConfigReloadedEvent(
                config_name=config_name,
                path=config_path,
                config_dict=after_plain,
                content_hash=outcome.content_hash,
                source=source,
                revision=outcome.revision,
                changed_keys=resolved_changed_keys,
            )
            if not self._deps.event_bus.try_publish_nowait(reload_event):
                publish_exception = ConfigurationError(
                    f"Failed to publish ConfigReloadedEvent for '{config_name}': EventBus refused enqueue.",
                )
                log_exception(
                    self._deps.logger,
                    publish_exception,
                    message="Failed to publish ConfigReloadedEvent",
                    operation=OPERATION,
                    details={"config_name": config_name},
                )
                try:
                    await rollback_after_publish_failure(
                        outcome,
                        reconciler=self._deps.reconciler,
                        cache=self._deps.cache,
                        logger=self._deps.logger,
                        in_file_lock=True,
                    )
                except ConfigurationError as rollback_exception:
                    raise ConfigurationError(
                        f"Failed to rollback failed publish for '{config_name}': {rollback_exception}",
                    ) from rollback_exception
                raise publish_exception
        return (outcome, after_plain, resolved_changed_keys)
