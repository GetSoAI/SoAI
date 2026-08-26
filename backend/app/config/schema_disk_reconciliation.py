"""SoAI - Config schema disk reconciliation helpers [backend/app/config/schema_disk_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from core.config.default_schema.schema import build_default_config_schema
from core.config.default_schema.yaml_generation import ensure_default_config_yaml
from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.config.migrations.runner import upgrade_config_payload_to_current
from core.config.schema_reconciliation import reconcile_config_schema
from core.config.value_validation import is_config_value
from core.config.yaml_factory import build_roundtrip_yaml
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "ConfigSchemaDiskReconciliationResult",
    "coerce_config_yaml_mapping",
    "ensure_default_config_schema_file",
    "load_config_yaml_or_create",
    "reconcile_config_payload",
    "reconcile_config_payload_on_disk",
    "resolve_default_config_schema_path",
    "write_config_yaml_sync",
)


@dataclass(frozen=True, slots=True)
class ConfigSchemaDiskReconciliationResult:
    data: ConfigDict
    backup_path: str | None
    changed_paths: tuple[str, ...]
    applied_migrations: tuple[str, ...]
    created: bool


def resolve_default_config_schema_path(config_path: str) -> str:
    return os.path.join(os.path.dirname(config_path), "config.default.yaml")


def ensure_default_config_schema_file(
    *,
    config_path: str,
    logger: LoggerProtocol,
    default_config_path: str | None = None,
) -> ConfigDict:
    schema = build_default_config_schema()
    ensure_default_config_yaml(
        default_config_path or resolve_default_config_schema_path(config_path),
        schema=schema,
        logger=logger,
    )
    return schema


def write_config_yaml_sync(
    *,
    path: str,
    data: ConfigDict,
    backup_path: str | None,
) -> None:
    yaml_dump = build_roundtrip_yaml()

    def writer(handle: io.TextIOBase) -> None:
        yaml_dump.dump(data, handle)

    secure_runtime_config_paths(path, backup_path)
    atomic_write_text(
        path,
        writer,
        encoding="utf-8",
        backup_path=backup_path,
        file_mode=runtime_config_atomic_file_mode(),
    )
    secure_runtime_config_paths(path, backup_path)


def coerce_config_yaml_mapping(value: ConfigValue, *, config_path: str) -> ConfigDict:
    if not isinstance(value, dict):
        raise ValueError(f"Config file is not a YAML mapping: {config_path}")
    result: ConfigDict = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"Config file contains an invalid key: {key!r}")
        if not is_config_value(item):
            raise ValueError(f"Config file contains an invalid value for key: {key}")
        result[key] = item
    return result


def load_config_yaml_or_create(
    *,
    config_path: str,
    logger: LoggerProtocol,
    create_missing: bool,
) -> tuple[ConfigDict, bool]:
    if not os.path.exists(config_path):
        if not create_missing:
            raise FileNotFoundError(config_path)
        config_data = build_default_config_schema()
        write_config_yaml_sync(path=config_path, data=config_data, backup_path=None)
        logger.info("Created missing config.yaml from the current V1 schema: %s", config_path)
        return (config_data, True)
    secure_runtime_config_paths(config_path, f"{config_path}.backup")
    yaml_safe = YAML(typ="safe")
    try:
        with open_text(config_path, encoding="utf-8") as handle:
            loaded = yaml_safe.load(handle)
    except YAMLError as exception:
        raise ValueError(f"Config file contains invalid YAML: {config_path}") from exception
    return (coerce_config_yaml_mapping(loaded, config_path=config_path), False)


def reconcile_config_payload(
    *,
    payload: ConfigDict,
    schema: ConfigDict,
    logger: LoggerProtocol,
    migration_message: str,
) -> ConfigSchemaDiskReconciliationResult:
    migrated, applied_migrations = upgrade_config_payload_to_current(payload, logger=logger)
    applied_migration_names = tuple(str(item) for item in applied_migrations)
    if applied_migration_names:
        logger.warning(migration_message, list(applied_migration_names))
    outcome = reconcile_config_schema(schema=schema, user=migrated)
    return ConfigSchemaDiskReconciliationResult(
        data=outcome.merged,
        backup_path=None,
        changed_paths=tuple(str(item) for item in outcome.changed_paths),
        applied_migrations=applied_migration_names,
        created=False,
    )


def reconcile_config_payload_on_disk(
    *,
    config_path: str,
    logger: LoggerProtocol,
    create_missing: bool,
    default_config_path: str | None = None,
    migration_message: str,
    drift_message: str,
    changed_paths_message: str,
) -> ConfigSchemaDiskReconciliationResult:
    user_config, created = load_config_yaml_or_create(
        config_path=config_path,
        logger=logger,
        create_missing=create_missing,
    )
    schema = ensure_default_config_schema_file(
        config_path=config_path,
        logger=logger,
        default_config_path=default_config_path,
    )
    result = reconcile_config_payload(
        payload=user_config,
        schema=schema,
        logger=logger,
        migration_message=migration_message,
    )
    backup_path = f"{config_path}.backup" if os.path.isfile(config_path) else None
    should_write = bool(result.changed_paths or result.applied_migrations)
    if result.changed_paths:
        logger.warning(drift_message)
        logger.warning(changed_paths_message, list(result.changed_paths))
    if should_write:
        write_config_yaml_sync(
            path=config_path,
            data=result.data,
            backup_path=backup_path,
        )
    return ConfigSchemaDiskReconciliationResult(
        data=result.data,
        backup_path=backup_path if should_write else None,
        changed_paths=result.changed_paths,
        applied_migrations=result.applied_migrations,
        created=created,
    )
