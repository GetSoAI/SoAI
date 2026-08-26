"""SoAI - Early runtime record path resolution [backend/core/bootstrap/runtime_record_path.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from core.config.path_resolution import (
    ConfigPathResolutionError,
    resolve_config_file_path,
    resolve_path,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.meta.paths import join_data_abs
from core.types.json import JSONValue, is_json_dict

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "resolve_runtime_record_path",
    "resolve_temp_directory_bootstrap",
)

OPERATION = "core.bootstrap.runtime_record_path.resolve_temp_directory_bootstrap"
DEFAULT_SYSTEM_DATA_PATH = "data"


def _mapping_text_value(mapping: Mapping[str, JSONValue], key: str) -> str | None:
    value = mapping.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _resolve_configured_temp_path(
    *,
    base_dir: str,
    system_paths: Mapping[str, JSONValue],
    default_path: str,
) -> str:
    system_data_value = _mapping_text_value(system_paths, "SYSTEM_DATA") or DEFAULT_SYSTEM_DATA_PATH
    system_data_path = resolve_path(system_data_value, base_dir)
    if system_data_path is None:
        return default_path
    temp_path_value = _mapping_text_value(system_paths, "TEMP")
    if temp_path_value is None:
        return default_path
    resolved = resolve_path(temp_path_value, system_data_path)
    if resolved is None:
        return default_path
    return os.path.abspath(resolved)


def resolve_temp_directory_bootstrap(base_dir: str, *, logger: LoggerProtocol) -> str:
    config_path = resolve_config_file_path(
        base_dir,
        configured_path=os.environ.get("SOAI_CONFIG_PATH", ""),
    )
    default_path = join_data_abs(base_dir, "temp")
    if not os.path.exists(config_path):
        return default_path
    try:
        parser = YAML(typ="safe")
        with open_text(config_path, encoding="utf-8") as handle:
            config_data = parser.load(handle)
    except YAMLError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to load SYSTEM.PATHS.TEMP from config; using default (non-critical).",
            operation=OPERATION,
            details={"config_path": config_path},
            level="debug",
        )
        return default_path
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to load SYSTEM.PATHS.TEMP from config; using default (non-critical).",
            operation=OPERATION,
            details={"config_path": config_path},
            level="debug",
        )
        return default_path
    if not is_json_dict(config_data):
        return default_path
    system_config = config_data.get("SYSTEM")
    system_paths = system_config.get("PATHS") if is_json_dict(system_config) else None
    if not is_json_dict(system_paths):
        return default_path
    try:
        return _resolve_configured_temp_path(
            base_dir=base_dir,
            system_paths=system_paths,
            default_path=default_path,
        )
    except ConfigPathResolutionError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to resolve SYSTEM.PATHS.TEMP from config; using default (non-critical).",
            operation=OPERATION,
            details={"config_path": config_path},
            level="debug",
        )
        return default_path


def resolve_runtime_record_path(base_dir: str, *, logger: LoggerProtocol) -> str:
    return os.path.join(
        resolve_temp_directory_bootstrap(base_dir, logger=logger),
        "soai.pid",
    )
