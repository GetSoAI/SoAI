"""SoAI - Atomic YAML configuration file I/O with locking [backend/app/config/io.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
import io
import os
from dataclasses import dataclass

from filelock import Timeout
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from app.config.paths import get_config_path_sync, path_to_config_name
from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.config.locks import ConfigLockTimeout, get_lock_path, resolve_lock_directory
from core.config.types import KnownFileState
from core.config.yaml_factory import build_roundtrip_yaml
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.hashing import calculate_file_hash
from core.filesystem.open_files import open_binary
from core.logging.protocols import LoggerProtocol

__all__ = (
    "ConfigIO",
    "ConfigIODependencies",
)

OPERATION_CONFIG_MANAGER_PARSE_CONFIG_CONTENTS = "config_manager.parse_config_contents"
OPERATION_CONFIG_MANAGER_READ_CONFIG_SNAPSHOT = "config_manager.read_config_snapshot"
OPERATION_CONFIG_MANAGER_READ_CONFIG_SNAPSHOT_UNLOCKED = (
    "config_manager.read_config_snapshot_unlocked"
)


_YAML_PARSE_ERRORS: tuple[type[Exception], ...] = (YAMLError,)


def _read_file_snapshot(config_path: str) -> tuple[bytes, os.stat_result]:
    secure_runtime_config_paths(config_path, f"{config_path}.backup")
    with open_binary(config_path, mode="rb") as handle:
        raw_bytes = handle.read()
        status = os.fstat(handle.fileno())
    return raw_bytes, status


def _decode_file_snapshot(raw_bytes: bytes, config_path: str) -> tuple[str, str]:
    current_hash = hashlib.sha256(raw_bytes).hexdigest()
    try:
        raw_contents = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise ConfigurationError(
            f"Config file is not valid UTF-8: {config_path}",
        ) from exception
    return raw_contents, current_hash


@dataclass(frozen=True, slots=True)
class ConfigIODependencies:
    base_path: str
    core_config_path: str
    plugins_path: str | None
    lock_directory: str | None
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigIODependencies",
            base_path=self.base_path,
            core_config_path=self.core_config_path,
            logger=self.logger,
        )


class ConfigIO:
    def __init__(self, deps: ConfigIODependencies) -> None:
        self._deps = deps
        self.base_path = deps.base_path
        self.plugins_path = deps.plugins_path
        self.lock_directory = resolve_lock_directory(deps.lock_directory)
        self._yaml_parse = YAML(typ="safe")

    def get_config_path_sync(self, config_name: str) -> str:
        return get_config_path_sync(
            core_config_path=self._deps.core_config_path,
            plugins_path=self.plugins_path,
            config_name=config_name,
        )

    def path_to_config_name(self, path: str) -> str | None:
        return path_to_config_name(
            core_config_path=self._deps.core_config_path,
            plugins_path=self.plugins_path,
            path=path,
        )

    def parse_config_contents(
        self,
        raw_contents: str,
        *,
        config_name: str,
        config_path: str,
    ) -> CommentedMap:
        try:
            data = self._yaml_parse.load(raw_contents)
        except _YAML_PARSE_ERRORS as exception:
            raise ConfigurationError(
                f"Error parsing YAML file {config_path}: {exception}",
            ) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced_exception = coerce_to_soai_error(
                exception,
                operation="config_manager.parse_config_contents",
            )
            log_exception(
                self._deps.logger,
                coerced_exception,
                message="Unexpected error parsing YAML file",
                operation=OPERATION_CONFIG_MANAGER_PARSE_CONFIG_CONTENTS,
                details={"config_name": config_name, "config_path": config_path},
            )
            raise ConfigurationError(
                f"Unexpected error parsing YAML file {config_path}: {coerced_exception}",
            ) from coerced_exception
        if data is None:
            return CommentedMap()
        if isinstance(data, dict):
            return CommentedMap(data)
        raise ConfigurationError(f"Config file for '{config_name}' is not a valid YAML mapping.")

    async def read_config_snapshot(
        self,
        *,
        config_path: str,
        config_name: str,
    ) -> tuple[str, str | None]:
        lock_path = get_lock_path(config_path, lock_directory=self.lock_directory)

        def _on_lock_timeout(_: Timeout) -> Exception:
            return ConfigLockTimeout(
                f"Could not acquire lock on {config_path}.",
                config_path=config_path,
            )

        try:
            async with async_guarded_file_lock(lock_path, timeout=5, on_timeout=_on_lock_timeout):
                raw_bytes, _ = await asyncio.to_thread(_read_file_snapshot, config_path)
                raw_contents, current_hash = _decode_file_snapshot(raw_bytes, config_path)
            return (raw_contents, current_hash)
        except PermissionError as exception:
            raise ConfigurationError(
                f"PERMISSION DENIED while reading config file: {config_path}.",
            ) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logger,
                exception,
                message="Error reading config",
                operation=OPERATION_CONFIG_MANAGER_READ_CONFIG_SNAPSHOT,
                details={"config_name": config_name},
            )
            raise ConfigurationError(
                f"Unexpected error reading config '{config_name}': {exception}",
            ) from exception

    async def read_config_snapshot_unlocked(
        self,
        *,
        config_path: str,
        config_name: str,
    ) -> tuple[str, str | None]:
        try:
            raw_bytes, _ = await asyncio.to_thread(_read_file_snapshot, config_path)
            raw_contents, current_hash = _decode_file_snapshot(raw_bytes, config_path)
            return (raw_contents, current_hash)
        except PermissionError as exception:
            raise ConfigurationError(
                f"PERMISSION DENIED while reading config file: {config_path}.",
            ) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logger,
                exception,
                message="Error reading config",
                operation=OPERATION_CONFIG_MANAGER_READ_CONFIG_SNAPSHOT_UNLOCKED,
                details={"config_name": config_name},
            )
            raise ConfigurationError(
                f"Unexpected error reading config '{config_name}': {exception}",
            ) from exception

    async def read_config_baseline_snapshot_unlocked(
        self,
        *,
        config_path: str,
        config_name: str,
    ) -> tuple[CommentedMap, KnownFileState]:
        try:
            raw_bytes, status = await asyncio.to_thread(_read_file_snapshot, config_path)
            raw_contents, current_hash = _decode_file_snapshot(raw_bytes, config_path)
            config_mapping = self.parse_config_contents(
                raw_contents,
                config_name=config_name,
                config_path=config_path,
            )
            return config_mapping, KnownFileState(
                mtime=status.st_mtime,
                size=status.st_size,
                content_hash=current_hash,
            )
        except PermissionError as exception:
            raise ConfigurationError(
                f"PERMISSION DENIED while reading config file: {config_path}.",
            ) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logger,
                exception,
                message="Error reading config baseline snapshot",
                operation=OPERATION_CONFIG_MANAGER_READ_CONFIG_SNAPSHOT_UNLOCKED,
                details={"config_name": config_name},
            )
            raise ConfigurationError(
                f"Unexpected error reading config '{config_name}': {exception}",
            ) from exception

    async def read_config_from_disk(self, *, config_name: str) -> CommentedMap | None:
        config_path = self.get_config_path_sync(config_name)
        exists = await asyncio.to_thread(os.path.exists, config_path)
        if not exists:
            return None
        raw_contents, _ = await self.read_config_snapshot(
            config_path=config_path,
            config_name=config_name,
        )
        return self.parse_config_contents(
            raw_contents,
            config_name=config_name,
            config_path=config_path,
        )

    async def calculate_file_hash(self, path: str) -> str | None:
        try:
            file_hash = await calculate_file_hash(path)
        except RECOVERABLE_EXCEPTIONS as exception:
            raise ConfigurationError(
                f"Failed to calculate file hash for '{path}': {exception}",
            ) from exception
        if file_hash is None or isinstance(file_hash, str):
            return file_hash
        raise ValidationError(f"calculate_file_hash returned unsupported type {type(file_hash)!r}")

    async def atomic_write_yaml_unlocked(
        self,
        *,
        config_path: str,
        config_mapping: CommentedMap,
        backup_path: str | None,
        encoding: str,
    ) -> None:
        def _writer(handle: io.TextIOBase) -> None:
            build_roundtrip_yaml().dump(config_mapping, handle)

        await asyncio.to_thread(secure_runtime_config_paths, config_path, backup_path)
        await asyncio.to_thread(
            atomic_write_text,
            config_path,
            _writer,
            encoding=encoding,
            backup_path=backup_path,
            file_mode=runtime_config_atomic_file_mode(),
        )
        await asyncio.to_thread(secure_runtime_config_paths, config_path, backup_path)
