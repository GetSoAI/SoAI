"""SoAI - Updater configuration loading [backend/app/updater/service_config_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.config.schema_disk_reconciliation import (
    coerce_config_yaml_mapping,
    reconcile_config_payload,
)
from core.config.default_schema.schema import build_default_config_schema
from core.config.layout import resolve_base_path
from core.config.path_resolution import resolve_default_config_schema_path
from core.config.value_validation import is_config_dict
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from core.meta.paths import get_repo_root

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("read_updater_config", "require_unchanged_update_configuration")

LOGGER_NAME = "SoAI.app.updater.service_config_loading"
OPERATION = "updater.read_updater_config.schema_load"


def require_unchanged_update_configuration(
    *,
    config_path: str,
    base_path: str,
    prepared_config: ConfigProtocol,
    module_dependencies: ApplicationUpdaterModuleDependencies,
) -> None:
    read_ok, current_base_path, current_config = read_updater_config(
        config_path=config_path, module_dependencies=module_dependencies
    )
    if not read_ok or current_config is None:
        raise StateError("Update configuration cannot be revalidated before installation.")
    if os.path.normcase(current_base_path) != os.path.normcase(base_path) or any(
        current_config.get(section) != prepared_config.get(section)
        for section in ("SYSTEM", "DATA", "PLUGINS", "MODELS")
    ):
        raise StateError(
            "Configuration affecting protected update state changed during preparation. Retry the update after configuration changes finish."
        )


def read_updater_config(
    *,
    config_path: str,
    module_dependencies: ApplicationUpdaterModuleDependencies,
) -> tuple[bool, str, ConfigProtocol | None]:
    recoverable_exceptions = RECOVERABLE_EXCEPTIONS + (OSError, module_dependencies.yaml.YAMLError)
    try:
        yaml_parser = module_dependencies.yaml.YAML(typ="safe")
        with open_text(config_path, encoding="utf-8") as file_handle:
            loaded = yaml_parser.load(file_handle)
        if not is_config_dict(loaded):
            sys.stderr.write(
                f"FATAL: Config file '{config_path}' is not a valid YAML dictionary.\n",
            )
            return False, "", None
        loaded = coerce_config_yaml_mapping(loaded, config_path=config_path)
        default_path = resolve_default_config_schema_path(config_path)
        try:
            logger = get_logger(LOGGER_NAME)
            schema = build_default_config_schema()
            reconciliation = reconcile_config_payload(
                payload=loaded,
                schema=schema,
                logger=logger,
                migration_message="Updater: Config migrations applied: %s",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Could not apply code-first config schema. Aborting updater config load.",
                operation=OPERATION,
                details={"schema_path": default_path},
                level="error",
            )
            sys.stderr.write(f"FATAL: Could not apply code-first config schema: {exception}\n")
            return False, "", None
        loaded = reconciliation.data
        system_value = loaded.get("SYSTEM")
        core_paths = system_value.get("PATHS") if is_config_dict(system_value) else None
        base_path_value = core_paths.get("BASE") if is_config_dict(core_paths) else None
        configured_base_path = (
            base_path_value
            if isinstance(base_path_value, str) and base_path_value.strip()
            else None
        )
        base_path = resolve_base_path(
            default_base_path=get_repo_root(),
            configured_base_path=configured_base_path,
            main_app_base_dir=None,
        )
        config = module_dependencies.config_factory(loaded, main_app_base_dir=base_path)
        return True, base_path, config
    except recoverable_exceptions as exception:
        sys.stderr.write(
            f"FATAL: Could not read or parse config file '{config_path}': {exception}\n",
        )
        return False, "", None
