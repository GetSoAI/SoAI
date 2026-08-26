"""SoAI - Application updater service coordinating software and plugin updates [backend/app/updater/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import platform
import sys
from dataclasses import dataclass

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.edition_composition import UpdaterComposition
from app.updater.api_client import UpdaterApiClient
from app.updater.dependencies import (
    PluginUpdateServiceDependencies,
    SoftwareUpdateServiceDependencies,
    UpdaterApiClientDependencies,
)
from app.updater.errors import UpdaterArgs
from app.updater.formatting import setup_logging
from app.updater.path_normalization import normalize_base_path, resolve_main_py_path
from app.updater.path_resolution import UpdaterFilesPathResolver
from app.updater.plugin_update import PluginUpdateService
from app.updater.service_config_loading import read_updater_config
from app.updater.service_version_detection import detect_local_version
from app.updater.software_update.service import SoftwareUpdateService
from app.updater.venv_check import check_venv_updates
from app.updater.version_paths import resolve_version_py_path
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from hardware.storage.dependencies import StorageManagerDependencies
from hardware.storage.manager import StorageManager

__all__ = (
    "Updater",
    "UpdaterDependencies",
)

LOGGER_NAME = "SoAI.app.updater.service"
OPERATION = "application_updater.initialize"


@dataclass(frozen=True, slots=True)
class UpdaterDependencies:
    args: UpdaterArgs
    module_dependencies: ApplicationUpdaterModuleDependencies
    updater: UpdaterComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="UpdaterDependencies",
            args=self.args,
            module_dependencies=self.module_dependencies,
            updater=self.updater,
        )


class Updater:
    def __init__(self, deps: UpdaterDependencies) -> None:
        self.args = deps.args
        self.config_path = os.path.abspath(deps.args.config)
        self.logger: StandardLogger = get_logger(LOGGER_NAME)
        self.base_path = ""
        self.temp_path = ""
        self.platform_name = platform.system()
        self.platform_id: str | None = None
        self.config: ConfigProtocol | None = None
        self.local_version: str | None = None
        self.main_py_path: str | None = None
        self.timeout = 10.0
        self.api_timeout = 30.0
        self.download_timeout = 3600.0
        self.stream_timeout = 7200.0
        self.module_dependencies = deps.module_dependencies
        self.updater = deps.updater

    def run(self) -> int:
        if not self._initialize():
            return 1
        config = self.config
        if config is None:
            raise ValidationError("Updater configuration is not initialized.")
        api_client_deps = UpdaterApiClientDependencies(
            logger=self.logger,
            module_dependencies=self.module_dependencies,
            config=config,
            base_path=self.base_path,
            args=self.args,
            edition=self.updater.edition,
        )
        api_client = UpdaterApiClient(api_client_deps)
        plugin_update_deps = PluginUpdateServiceDependencies(
            args=self.args,
            logger=self.logger,
            api_client=api_client,
            api_timeout=self.api_timeout,
            stream_timeout=self.stream_timeout,
        )
        plugin_update_service = PluginUpdateService(plugin_update_deps)
        storage_manager = StorageManager(
            StorageManagerDependencies(
                config=config,
                files=UpdaterFilesPathResolver(self.base_path),
                base_dir=self.base_path,
            ),
        )
        software_update_deps = SoftwareUpdateServiceDependencies(
            args=self.args,
            logger=self.logger,
            api_client=api_client,
            module_dependencies=self.module_dependencies,
            config=config,
            config_path=self.config_path,
            base_path=self.base_path,
            temp_path=self.temp_path,
            platform_name=self.platform_name,
            platform_id=self.platform_id,
            main_py_path=self.main_py_path,
            local_version=self.local_version,
            timeout=self.timeout,
            api_timeout=self.api_timeout,
            download_timeout=self.download_timeout,
            storage_manager=storage_manager,
            updater=self.updater,
        )
        software_update_service = SoftwareUpdateService(software_update_deps)
        if self.args.check_update_software:
            return software_update_service.run_software_update_check()
        if self.args.check_update_plugins:
            return plugin_update_service.run_plugin_update_check()
        if self.args.check_update_venv:
            return check_venv_updates(base_path=self.base_path, logger=self.logger)
        if self.args.update_plugins:
            return plugin_update_service.run_plugin_update()
        if self.args.update_software:
            return software_update_service.run_software_update()
        self.logger.warning("No valid action specified. Use --help to see options.")
        return 1

    def _initialize(self) -> bool:
        if not os.path.exists(self.config_path):
            sys.stderr.write(f"FATAL: Configuration file not found at '{self.config_path}'\n")
            return False
        read_ok, resolved_base_path, loaded_config = read_updater_config(
            config_path=self.config_path,
            module_dependencies=self.module_dependencies,
        )
        if not read_ok:
            return False
        self.base_path = resolved_base_path
        self.config = loaded_config
        config = self.config
        if config is None:
            raise ValidationError("Updater configuration is not initialized.")
        stay_offline = self.module_dependencies.coerce_bool_with_default(
            config.get("SYSTEM.RUNTIME.STAY_OFFLINE"),
            default=False,
        )
        if stay_offline:
            sys.stderr.write(
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled. Software updates are disabled in offline mode.\n",
            )
            return False
        self.main_py_path = resolve_main_py_path(
            self.base_path,
            self.updater.entrypoint_relative_path,
        )
        log_path = config.get_str("OBSERVABILITY.LOGGING.LOGS_PATH")
        if log_path is None or not log_path.strip():
            sys.stderr.write("FATAL: OBSERVABILITY.LOGGING.LOGS_PATH is missing.\n")
            return False
        if not os.path.isabs(log_path):
            log_path = os.path.join(self.base_path, log_path)
        log_path = os.path.abspath(log_path)
        forbidden_log_path = os.path.join(os.path.abspath(self.base_path), "logs")
        if log_path == forbidden_log_path or log_path.startswith(forbidden_log_path + os.sep):
            sys.stderr.write(
                "FATAL: OBSERVABILITY.LOGGING.LOGS_PATH must not target the base path logs directory.\n",
            )
            return False
        temp_value = config.get_str("SYSTEM.PATHS.TEMP")
        if temp_value is None or not temp_value.strip():
            sys.stderr.write("FATAL: SYSTEM.PATHS.TEMP is missing.\n")
            return False
        if not os.path.isabs(temp_value):
            temp_value = os.path.join(self.base_path, temp_value)
        self.temp_path = os.path.abspath(temp_value)
        self.timeout = self.module_dependencies.coerce_positive_float(
            config.get("SYSTEM.UPDATER.TIMEOUT_SEC", 10),
            default=10.0,
            minimum=1.0,
        )
        self.api_timeout = self.module_dependencies.coerce_positive_float(
            config.get("SYSTEM.UPDATER.API_TIMEOUT_SEC", 30),
            default=30.0,
            minimum=1.0,
        )
        self.download_timeout = self.module_dependencies.coerce_positive_float(
            config.get("SYSTEM.UPDATER.DOWNLOAD_TIMEOUT_SEC", 3600),
            default=3600.0,
            minimum=10.0,
        )
        self.stream_timeout = self.module_dependencies.coerce_positive_float(
            config.get("SYSTEM.UPDATER.STREAM_TIMEOUT_SEC", 7200),
            default=7200.0,
            minimum=10.0,
        )
        self.platform_id = get_runtime_platform().platform_id
        self.logger = setup_logging(
            os.path.join(log_path, "application_updater.log"),
            logging.DEBUG if self.args.debug else logging.INFO,
        )
        if not self._normalize_base_path():
            return False
        try:
            os.makedirs(self.temp_path, exist_ok=True)
        except OSError as exception:
            log_exception(
                self.logger,
                exception,
                message="Failed to prepare temp directory",
                operation=OPERATION,
                details={"path": self.temp_path},
            )
            return False
        if not self.main_py_path or not os.path.exists(self.main_py_path):
            self.logger.error(
                "Main application entrypoint not found at '%s'.",
                self.main_py_path or "",
            )
            return False
        version_py_path = resolve_version_py_path(self.base_path)
        if not os.path.exists(version_py_path):
            self.logger.error("Version module not found at '%s'.", version_py_path)
            return False
        self.local_version = detect_local_version(
            module_dependencies=self.module_dependencies,
            logger=self.logger,
            base_path=self.base_path,
            main_py_path=self.main_py_path,
        )
        if not self.local_version and self.args.check_update_software:
            return False
        if config.get("SYSTEM.RUNTIME.HOST_SYSTEM_ACTIONS_DISABLED"):
            self.logger.info(
                "Host system actions are disabled. Automatic software updates are not applicable.",
            )
            return False
        return True

    def _normalize_base_path(self) -> bool:
        resolved_base = normalize_base_path(self.base_path, logger=self.logger)
        if resolved_base is None:
            return False
        self.base_path = resolved_base
        self.main_py_path = resolve_main_py_path(
            self.base_path,
            self.updater.entrypoint_relative_path,
        )
        return True
