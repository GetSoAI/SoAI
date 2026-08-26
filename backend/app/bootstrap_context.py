"""SoAI - Resilient bootstrap configuration loading [backend/app/bootstrap_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from app.application_dependencies import ApplicationBootstrapModuleDependencies
from app.bootstrap_config_value_coercion import coerce_bootstrap_config_value
from app.bootstrap_degraded_config import build_degraded_bootstrap_config
from app.bootstrap_yaml_loader import load_and_parse_yaml, normalize_loaded_config
from app.config.schema_disk_reconciliation import (
    ensure_default_config_schema_file,
    reconcile_config_payload,
    write_config_yaml_sync,
)
from core.config.default_schema.schema import build_default_config_schema
from core.errors.exception_logging import log_exception
from core.filesystem.async_queries import async_path_exists
from core.logging.trace import get_logger
from core.meta.paths import join_data_abs

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict
    from core.logging.protocols import LoggerProtocol

__all__ = ("BootstrapContext",)

LOGGER_NAME = "SoAI.app.bootstrap_context"
OPERATION_APPLICATION_BOOTSTRAP_LOAD_AND_PARSE_YAML = "application_bootstrap.load_and_parse_yaml"
OPERATION_APPLICATION_BOOTSTRAP_LOAD_CONFIGURATION = "application_bootstrap.load_configuration"
OPERATION_APPLICATION_BOOTSTRAP_LOAD_CONFIGURATION_GENERATE_DEFAULT_CONFIG = (
    "application_bootstrap.load_configuration.generate_default_config"
)


class BootstrapContext:
    def __init__(
        self,
        base_dir: str,
        config_path: str,
        module_dependencies: ApplicationBootstrapModuleDependencies,
        yaml_parser: YAML | None = None,
        degraded_provider: Callable[[], ConfigDict] | None = None,
        lifecycle_logger: LoggerProtocol | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.config_path = config_path
        self.module_dependencies = module_dependencies
        self.yaml_parser = (
            yaml_parser
            if yaml_parser is not None
            else YAML(typ="safe") if YAML is not None else None
        )
        self.degraded_mode = False
        self._degraded_provider = degraded_provider
        self._logger = lifecycle_logger or get_logger(LOGGER_NAME)

    async def load_and_parse_yaml(self, path: str) -> ConfigDict | None:
        try:
            if not await async_path_exists(path):
                return None
            return await load_and_parse_yaml(
                path,
                yaml_loader=self.yaml_parser,
                logger=self._logger,
                normalize=lambda data: normalize_loaded_config(
                    data,
                    config_path=path,
                    logger=self._logger,
                    coerce_item=lambda item: coerce_bootstrap_config_value(item, config_path=path),
                ),
            )
        except PermissionError:
            self._logger.critical(
                "FATAL: Unrecoverable permission error while trying to read '%s'. Cannot start.",
                path,
            )
            raise
        except FileNotFoundError:
            self._logger.warning("Configuration file at '%s' is missing.", path)
            return None
        except (OSError, TypeError, ValueError) as error:
            log_exception(
                self._logger,
                error,
                message=f"An unexpected error occurred while reading '{path}'",
                operation=OPERATION_APPLICATION_BOOTSTRAP_LOAD_AND_PARSE_YAML,
            )
            return None

    def get_degraded_mode_config(self) -> ConfigDict:
        if self._degraded_provider:
            config = self._degraded_provider()
            self.degraded_mode = True
            return config
        self._logger.critical(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
        )
        self._logger.critical(
            "!!! CRITICAL: No valid configuration file found.                             !!!",
        )
        self._logger.critical(
            "!!! SoAI is starting in a limited, DEGRADED MODE with default settings.      !!!",
        )
        self._logger.critical(
            "!!! Please create a 'config.yaml' file to restore full functionality.        !!!",
        )
        self._logger.critical(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
        )
        self.degraded_mode = True
        return build_degraded_bootstrap_config(base_dir=self.base_dir)

    async def load_configuration(self) -> tuple[ConfigDict, bool]:
        self._logger.debug("Bootstrap: Starting resilient configuration loading for 'core' config.")
        if self.yaml_parser is None:
            return (self.get_degraded_mode_config(), True)
        default_config_path = join_data_abs(self.base_dir, "config", "config.default.yaml")

        try:
            default_config_data = await asyncio.to_thread(
                ensure_default_config_schema_file,
                config_path=self.config_path,
                logger=self._logger,
                default_config_path=default_config_path,
            )
        except PermissionError:
            self._logger.critical(
                "FATAL: Unrecoverable permission error while trying to write '%s'. Cannot start.",
                default_config_path,
            )
            raise
        except (OSError, ValueError, TypeError) as error:
            log_exception(
                self._logger,
                error,
                message=("Bootstrap: Failed to generate 'config.default.yaml' from code schema"),
                operation=(
                    OPERATION_APPLICATION_BOOTSTRAP_LOAD_CONFIGURATION_GENERATE_DEFAULT_CONFIG
                ),
            )
            default_config_data = build_default_config_schema()

        config_exists = await async_path_exists(self.config_path)
        user_config_data = (
            await self.load_and_parse_yaml(self.config_path) if config_exists else None
        )

        async def _write_bootstrap_config_yaml(data: ConfigDict) -> bool:
            backup_path = (
                f"{self.config_path}.backup" if await async_path_exists(self.config_path) else None
            )
            await asyncio.to_thread(
                write_config_yaml_sync,
                path=self.config_path,
                data=data,
                backup_path=backup_path,
            )
            return True

        if user_config_data is None:
            self._logger.warning(
                "Bootstrap: 'config.yaml' is missing or corrupt. Restoring from schema 'config.default.yaml'...",
            )
            try:
                await _write_bootstrap_config_yaml(default_config_data)
                restored_data = await self.load_and_parse_yaml(self.config_path)
                if restored_data is not None:
                    return (restored_data, False)
                self._logger.critical(
                    "Bootstrap: Restored 'config.yaml' but failed to reload it. The schema file may be corrupt.",
                )
            except PermissionError:
                raise
            except OSError as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Bootstrap: CRITICAL - Failed to restore 'config.yaml' from schema",
                    operation=OPERATION_APPLICATION_BOOTSTRAP_LOAD_CONFIGURATION,
                )
            return (self.get_degraded_mode_config(), True)

        reconciliation = reconcile_config_payload(
            payload=user_config_data,
            schema=default_config_data,
            logger=self._logger,
            migration_message="Bootstrap: Config migrations applied: %s",
        )
        merged_config = reconciliation.data
        should_write_config = bool(
            reconciliation.changed_paths or reconciliation.applied_migrations,
        )
        if reconciliation.changed_paths:
            self._logger.warning(
                "Bootstrap: Config schema drift detected; rewriting config.yaml to match config.default.yaml.",
            )
            self._logger.warning(
                "Bootstrap: Updated config paths: %s",
                list(reconciliation.changed_paths),
            )
        if should_write_config:
            await _write_bootstrap_config_yaml(merged_config)
        self._logger.debug("Bootstrap: Successfully loaded and reconciled 'config.yaml'.")
        self._logger.info("Configuration loaded: %s", self.config_path)
        return (merged_config, False)
