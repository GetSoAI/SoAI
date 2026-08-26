"""SoAI - Bootstrap SYSTEM.PATHS.BASE validation and correction [backend/app/config/base_path_correction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from filelock import Timeout
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from core.config.dotted_key_access import get_nested_config_value
from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.config.locks import get_lock_path, resolve_lock_directory
from core.config.yaml_factory import build_roundtrip_yaml
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "BasePathCorrectionResult",
    "BasePathCorrectionService",
    "BasePathCorrectionServiceDependencies",
    "correct_base_path_in_config",
)

OPERATION = "base_path_correction.persist_correction_to_disk"


_BASE_PATH_KEY = "SYSTEM.PATHS.BASE"


def _config_mutable_mapping(value: ConfigValue | None) -> MutableMapping[str, ConfigValue] | None:
    if not isinstance(value, MutableMapping):
        return None
    return value


def _get_config_section(mapping: MutableMapping[str, ConfigValue], key: str) -> ConfigValue | None:
    return mapping.get(key)


@dataclass(frozen=True, slots=True)
class BasePathCorrectionServiceDependencies:
    config_path: str
    computed_base_dir: str
    lock_directory: str | None
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="BasePathCorrectionServiceDependencies",
            computed_base_dir=self.computed_base_dir,
            config_path=self.config_path,
            logger=self.logger,
        )


@dataclass(frozen=True, slots=True)
class BasePathCorrectionResult:
    was_corrected: bool
    previous_value: str | None
    current_value: str
    error_message: str | None


class BasePathCorrectionService:
    def __init__(self, deps: BasePathCorrectionServiceDependencies) -> None:
        self._deps = deps
        self._lock_directory = resolve_lock_directory(deps.lock_directory)
        self._yaml_roundtrip = build_roundtrip_yaml()

    async def correct_base_path_if_needed(
        self,
        config_data: MutableMapping[str, ConfigValue],
    ) -> BasePathCorrectionResult:
        current_value = config_data.get(_BASE_PATH_KEY)
        if current_value is None:
            current_value = get_nested_config_value(config_data, _BASE_PATH_KEY)
        computed_base_dir = self._deps.computed_base_dir

        if current_value == computed_base_dir:
            return BasePathCorrectionResult(
                was_corrected=False,
                previous_value=str(current_value) if current_value is not None else None,
                current_value=computed_base_dir,
                error_message=None,
            )

        previous_value = str(current_value) if current_value is not None else None
        system_mapping = _config_mutable_mapping(config_data.get("SYSTEM"))
        if system_mapping is None:
            new_system_mapping: MutableMapping[str, ConfigValue] = {}
            config_data["SYSTEM"] = new_system_mapping
            system_mapping = new_system_mapping
        paths_section = _get_config_section(system_mapping, "PATHS")
        paths_mapping = _config_mutable_mapping(paths_section)
        if paths_mapping is None:
            new_paths_mapping: MutableMapping[str, ConfigValue] = {}
            system_mapping["PATHS"] = new_paths_mapping
            paths_mapping = new_paths_mapping
        paths_mapping["BASE"] = computed_base_dir

        if current_value is None:
            self._deps.logger.info(
                "SYSTEM.PATHS.BASE was not set in config.yaml. Auto-populating with detected application directory: %s",
                computed_base_dir,
            )
        else:
            self._deps.logger.warning(
                "SYSTEM.PATHS.BASE mismatch detected. Config had '%s' but application directory is '%s'. Auto-correcting.",
                str(current_value),
                computed_base_dir,
            )

        error_message = await self._persist_correction_to_disk(computed_base_dir)

        return BasePathCorrectionResult(
            was_corrected=True,
            previous_value=previous_value,
            current_value=computed_base_dir,
            error_message=error_message,
        )

    async def _persist_correction_to_disk(self, new_base_path: str) -> str | None:
        config_path = self._deps.config_path
        if not os.path.exists(config_path):
            return (
                f"Config file does not exist at '{config_path}'; "
                "cannot persist SYSTEM.PATHS.BASE correction."
            )

        lock_path = get_lock_path(config_path, lock_directory=self._lock_directory)

        def _on_lock_timeout(_: Timeout) -> Exception:
            return ConfigurationError(
                f"Could not acquire lock to correct SYSTEM.PATHS.BASE in {config_path}.",
            )

        try:
            async with async_guarded_file_lock(lock_path, timeout=10, on_timeout=_on_lock_timeout):
                return await self._read_modify_write_config(config_path, new_base_path)
        except ConfigurationError as exception:
            error_msg = f"Failed to acquire lock for SYSTEM.PATHS.BASE correction: {exception}"
            self._deps.logger.error(error_msg)
            return error_msg
        except RECOVERABLE_EXCEPTIONS as exception:
            error_msg = f"Unexpected error during SYSTEM.PATHS.BASE correction: {exception}"
            log_exception(
                self._deps.logger,
                exception,
                message="Failed to persist SYSTEM.PATHS.BASE correction",
                operation=OPERATION,
                details={"config_path": config_path, "new_base_path": new_base_path},
            )
            return error_msg

    async def _read_modify_write_config(self, config_path: str, new_base_path: str) -> str | None:
        def _sync_read_modify_write() -> str | None:
            secure_runtime_config_paths(config_path)
            try:
                with open_text(config_path, mode="r", encoding="utf-8") as handle:
                    loaded_data = self._yaml_roundtrip.load(handle)
            except PermissionError as exception:
                return f"PERMISSION DENIED reading config file: {exception}"
            except YAMLError as exception:
                return f"Config file contains invalid YAML: {exception}"
            except OSError as exception:
                return f"Failed to read config file for SYSTEM.PATHS.BASE correction: {exception}"

            config_data: CommentedMap
            if loaded_data is None:
                config_data = CommentedMap()
            elif isinstance(loaded_data, CommentedMap):
                config_data = loaded_data
            elif isinstance(loaded_data, Mapping):
                config_data = CommentedMap(loaded_data)
            else:
                return f"Config file must be a YAML mapping, not {type(loaded_data).__name__}"

            system_section = config_data.get("SYSTEM")
            if not isinstance(system_section, MutableMapping):
                system_section = CommentedMap()
                config_data["SYSTEM"] = system_section
            paths_section = system_section.get("PATHS")
            if not isinstance(paths_section, MutableMapping):
                paths_section = CommentedMap()
                system_section["PATHS"] = paths_section
            paths_section["BASE"] = new_base_path

            backup_path = f"{config_path}.base_path_correction.backup"
            secure_runtime_config_paths(backup_path)

            def _writer(handle: io.TextIOBase) -> None:
                self._yaml_roundtrip.dump(config_data, handle)

            try:
                atomic_write_text(
                    config_path,
                    _writer,
                    encoding="utf-8",
                    backup_path=backup_path,
                    file_mode=runtime_config_atomic_file_mode(),
                )
                secure_runtime_config_paths(config_path, backup_path)
            except PermissionError as exception:
                return f"PERMISSION DENIED writing config file: {exception}"
            except OSError as exception:
                return (
                    "Failed to write config file after SYSTEM.PATHS.BASE correction: "
                    f"{exception}"
                )

            self._deps.logger.info(
                "Successfully persisted SYSTEM.PATHS.BASE correction to %s (backup at %s)",
                config_path,
                backup_path,
            )
            return None

        return await asyncio.to_thread(_sync_read_modify_write)


async def correct_base_path_in_config(
    *,
    config_data: MutableMapping[str, ConfigValue],
    config_path: str,
    computed_base_dir: str,
    lock_directory: str | None,
    logger: LoggerProtocol,
) -> BasePathCorrectionResult:
    deps = BasePathCorrectionServiceDependencies(
        config_path=config_path,
        computed_base_dir=computed_base_dir,
        lock_directory=lock_directory,
        logger=logger,
    )
    service = BasePathCorrectionService(deps)
    return await service.correct_base_path_if_needed(config_data)
