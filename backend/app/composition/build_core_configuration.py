"""SoAI - Core application configuration loading and initialization [backend/app/composition/build_core_configuration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from app.application_dependencies import (
    ApplicationEnvironment,
    ApplicationLogging,
    ApplicationModuleDependencies,
)
from app.bootstrap_context import BootstrapContext
from app.config.base_path_correction import correct_base_path_in_config
from app.config.commented_maps import build_commented_map
from app.config.service import ConfigManager
from app.updater.software_update.frontend_payload_validation import validate_staged_frontend
from core.config.dotted_key_access import get_nested_config_value
from core.config.protocols import ConfigProtocol
from core.config.runtime_config import Config
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import ensure_dirs_exist
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.routing_config_builders import build_routing_config
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeStateStoreProtocol
from core.serialization.json import normalize_for_json
from core.types.json import JSONValue
from core.types.json_value import coerce_json_dict
from core.validation.boolean_coercion import coerce_bool_with_default

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue
    from core.config.value_types import ConfigDict

__all__ = (
    "build_application_routing_config",
    "configure_platform_runtime",
    "configure_webui_defaults",
    "ensure_base_path_correct",
    "initialize_config_manager",
    "load_configuration_data",
    "resolve_pid_file_path",
    "validate_environment",
)

LOGGER_NAME = "SoAI.app.composition.build_core_configuration"
OPERATION = "application_builder.configure_webui_defaults"


def validate_environment(environment: ApplicationEnvironment) -> None:
    if not environment.base_dir:
        raise ValidationError("base_dir is required.")
    if not environment.config_path:
        raise ValidationError("config_path is required.")
    if not environment.main_venv_dir:
        raise ValidationError("main_venv_dir is required.")
    if not environment.version:
        raise ValidationError("version is required.")


async def load_configuration_data(
    *,
    environment: ApplicationEnvironment,
    module_dependencies: ApplicationModuleDependencies,
    logging_instance: ApplicationLogging,
) -> tuple[ConfigDict, bool]:
    bootstrap_context = BootstrapContext(
        base_dir=environment.base_dir,
        config_path=environment.config_path,
        module_dependencies=module_dependencies.bootstrap,
        yaml_parser=YAML(typ="safe"),
        lifecycle_logger=logging_instance.lifecycle_logger,
    )
    config_data, degraded_mode = await bootstrap_context.load_configuration()
    if "CONFIG_PATH" in config_data:
        raise ConfigurationError("CONFIG_PATH is reserved and must not be set in YAML.")
    config_data["CONFIG_PATH"] = environment.config_path
    return config_data, degraded_mode


async def ensure_base_path_correct(
    *,
    config_data: MutableMapping[str, ConfigValue],
    environment: ApplicationEnvironment,
    lifecycle_logger: LoggerProtocol,
) -> None:
    lock_directory_value = get_nested_config_value(config_data, "SYSTEM.PATHS.LOCKS")
    lock_directory = str(lock_directory_value) if isinstance(lock_directory_value, str) else None

    result = await correct_base_path_in_config(
        config_data=config_data,
        config_path=environment.config_path,
        computed_base_dir=environment.base_dir,
        lock_directory=lock_directory,
        logger=lifecycle_logger,
    )

    if result.was_corrected and result.error_message is not None:
        lifecycle_logger.warning(
            "SYSTEM.PATHS.BASE was corrected in memory but could not be persisted to disk: %s",
            result.error_message,
        )


def resolve_pid_file_path(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
) -> str:
    temp_path_value = config.get_str("SYSTEM.PATHS.TEMP")
    if not temp_path_value:
        raise ValidationError("SYSTEM.PATHS.TEMP must be configured.")
    resolved_temp_path = files.resolve_path(temp_path_value)
    return os.path.join(resolved_temp_path, "soai.pid")


def configure_webui_defaults(
    *,
    config: Config,
    files: FilesProtocol,
    runtime_state: RuntimeStateStoreProtocol,
    logging_instance: ApplicationLogging,
    base_dir: str,
    edition: str,
    webui_relative_path: str,
    webui_fallback_relative_paths: tuple[str, ...],
) -> None:
    webui_section = config.ensure_mapping("SERVER.WEBUI")
    enabled_value = webui_section.get("ENABLED")
    if (
        not isinstance(enabled_value, str | int | float | bool | bytes | bytearray)
        and enabled_value is not None
    ):
        raise ValidationError("SERVER.WEBUI.ENABLED must be a boolean.")
    desired_state = coerce_bool_with_default(enabled_value, default=True, strict=True)
    resolved_path_value = webui_relative_path
    config.set_value("SERVER.WEBUI.PATH", webui_relative_path)
    config.set_value("SERVER.WEBUI.FALLBACK_PATHS", list(webui_fallback_relative_paths))
    resolved_path: str | None = None
    resolved_fallback_paths: list[str] = []
    for fallback_path in webui_fallback_relative_paths:
        resolved_fallback_path = files.resolve_path(fallback_path)
        if not os.path.isdir(resolved_fallback_path):
            raise ValidationError(f"WebUI fallback path does not exist: {fallback_path}")
        resolved_fallback_paths.append(resolved_fallback_path)
    config.set_value("SERVER.WEBUI.FALLBACK_PATHS", resolved_fallback_paths)
    if isinstance(resolved_path_value, str | os.PathLike) and str(resolved_path_value).strip():
        raw_webui_path = resolved_path_value
        try:
            resolved_path = files.resolve_path(resolved_path_value)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logging_instance.logger,
                exception,
                message="Failed to resolve configured WebUI path (non-critical).",
                operation=OPERATION,
                details={"path": str(raw_webui_path)},
                level="debug",
            )
            resolved_path = None
    if desired_state and resolved_path and os.path.isdir(resolved_path):
        validate_staged_frontend(
            base_dir,
            frontend_relative_path=webui_relative_path,
            expected_edition=edition,
            fallback_relative_paths=webui_fallback_relative_paths,
        )
        runtime_state.set_webui_available(True)
        config.set_value("SERVER.WEBUI.PATH", resolved_path)
        return
    runtime_state.set_webui_available(False)
    if desired_state:
        logging_instance.logger.warning(
            "WebUI assets were not found; disabling WebUI features for this session.",
        )
    config.set_value("SERVER.WEBUI.ENABLED", False)
    config.set_value("SERVER.WEBUI.AUTO_OPEN_BROWSER", False)
    if resolved_path:
        config.set_value("SERVER.WEBUI.PATH", resolved_path)


async def configure_platform_runtime(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> None:
    if runtime_flags.host_system_actions_disabled:
        get_logger(LOGGER_NAME).info(
            "Host system actions are disabled by SYSTEM.RUNTIME.HOST_SYSTEM_ACTIONS_DISABLED.",
        )
    wallpaper_path = config.get_str("SERVER.WEBUI.WALLPAPER_STORAGE_PATH")
    if not wallpaper_path:
        raise ValidationError("SERVER.WEBUI.WALLPAPER_STORAGE_PATH must be configured.")
    files_storage_path = config.get_str("DATA.FILES.PATHS.FILES_STORAGE")
    if not files_storage_path:
        raise ValidationError("DATA.FILES.PATHS.FILES_STORAGE must be configured.")
    await ensure_dirs_exist([wallpaper_path, files_storage_path])


async def initialize_config_manager(
    *,
    config_manager: ConfigManager,
    configuration_data: Mapping[str, JSONValue],
) -> None:
    config_manager.configs["core"] = build_commented_map(configuration_data)
    await config_manager.rescan_and_update_baseline_for_config("core")


def build_application_routing_config(
    *,
    config: ConfigProtocol,
    logger: LoggerProtocol,
) -> RoutingConfig:
    routing_dict = config.get("MODELS.ROUTING", {})
    normalized = normalize_for_json(routing_dict)
    resolved = coerce_json_dict(normalized)
    return build_routing_config(resolved, logger)
