"""SoAI - Application configuration foundation assembly [backend/app/composition/build_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import (
    ApplicationEnvironment,
    ApplicationLogging,
    ApplicationModuleDependencies,
)
from app.composition.build_core_configuration import load_configuration_data
from app.edition_composition import EditionCapabilities
from core.config.layout import STATE_DOTTED_KEYS
from core.config.runtime_config import Config
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConfigurationError
from core.files.path_policy import is_path_within_base
from core.files.path_resolver import ConfigFilesPathResolver
from core.logging.trace import get_logger
from core.network.dns import configure_dns_override_servers
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.flags_service import (
    RuntimeFlagsService,
    RuntimeFlagsServiceDependencies,
)

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = (
    "ConfigurationFoundation",
    "build_configuration_foundation",
    "build_runtime_flags_service",
)

OPERATION_DNS_OVERRIDE_SERVERS = "app.composition.build_config.dns_override_servers"

LOGGER_NAME = "SoAI.app.composition.build_config"


@dataclass(slots=True, frozen=True)
class ConfigurationFoundation:
    config: Config
    files: FilesProtocol
    runtime_flags_service: RuntimeFlagsService
    configuration_data: ConfigDict
    degraded_mode: bool


def _resolve_dns_override_servers(
    config: Config,
) -> tuple[str, ...] | None:
    raw = config.get_str("SYSTEM.SECURITY.DNS_OVERRIDE_SERVERS")
    if not isinstance(raw, str):
        return None
    normalized = raw.strip()
    if not normalized:
        return None
    tokens = [part.strip() for part in normalized.replace(",", " ").split()]
    unique: list[str] = []
    for token in tokens:
        if not token:
            continue
        try:
            _ = ipaddress.ip_address(token)
        except ValueError as exception:
            raise ValueError(
                f"SYSTEM.SECURITY.DNS_OVERRIDE_SERVERS must contain only IP addresses; got: {token}",
            ) from exception
        if token not in unique:
            unique.append(token)
        if len(unique) >= 3:
            break
    return tuple(unique) if unique else None


def build_runtime_flags_service(
    *,
    config: Config,
    edition_capabilities: EditionCapabilities,
) -> RuntimeFlagsService:
    offline_mode = config.get_bool("SYSTEM.RUNTIME.STAY_OFFLINE")
    host_system_actions_disabled = config.get_bool(
        "SYSTEM.RUNTIME.HOST_SYSTEM_ACTIONS_DISABLED",
    )
    hardware_mutation_disabled = config.get_bool(
        "SYSTEM.RUNTIME.HARDWARE_MUTATION_DISABLED",
    )
    host_management_available = edition_capabilities.host_management_enabled
    block_private_network_egress = config.get_bool("SYSTEM.SECURITY.BLOCK_PRIVATE_NETWORK_EGRESS")
    dns_validation_timeout = config.get_float("SYSTEM.SECURITY.DNS_VALIDATION_TIMEOUT_SEC")
    if host_management_available and host_system_actions_disabled:
        get_logger(LOGGER_NAME).info(
            "SoAI OS mode detected; host management is disabled by runtime policy.",
        )
    elif host_management_available:
        get_logger(LOGGER_NAME).info("SoAI OS mode enabled.")
    runtime_flags_service = RuntimeFlagsService(
        RuntimeFlagsServiceDependencies(
            initial_host_system_actions_disabled=host_system_actions_disabled,
            initial_hardware_mutation_disabled=hardware_mutation_disabled,
            initial_offline_mode=offline_mode,
            initial_block_private_network_egress=block_private_network_egress,
            dns_validation_timeout_sec=dns_validation_timeout,
            initial_host_management_available=host_management_available,
        ),
    )
    return runtime_flags_service


def _validate_state_path_layout(*, config: Config) -> None:
    system_data_path = config.get_str("SYSTEM.PATHS.SYSTEM_DATA")
    if not system_data_path:
        raise ConfigurationError("SYSTEM.PATHS.SYSTEM_DATA must be configured.")

    resolved_system_data = os.path.realpath(os.path.abspath(system_data_path))
    try:
        os.makedirs(resolved_system_data, exist_ok=True)
    except OSError as exception:
        raise ConfigurationError(
            "Failed to create SYSTEM.PATHS.SYSTEM_DATA directory.",
            details={"SYSTEM.PATHS.SYSTEM_DATA": resolved_system_data},
            operation="config.validate_state_path_layout",
        ) from exception
    if not os.path.isdir(resolved_system_data):
        raise ConfigurationError(
            "SYSTEM.PATHS.SYSTEM_DATA must resolve to a directory.",
            details={"SYSTEM.PATHS.SYSTEM_DATA": resolved_system_data},
            operation="config.validate_state_path_layout",
        )

    violations: list[dict[str, str]] = []
    for key in sorted(STATE_DOTTED_KEYS):
        if key == "SYSTEM.PATHS.SYSTEM_DATA":
            continue
        value = config.get_str(key)
        if not value:
            continue
        resolved = os.path.realpath(os.path.abspath(value))
        if not is_path_within_base(resolved_system_data, resolved):
            violations.append({"key": key, "path": resolved})
    if violations:
        raise ConfigurationError(
            (
                "One or more runtime state paths are outside SYSTEM.PATHS.SYSTEM_DATA. "
                "Configure them to live under SYSTEM.PATHS.SYSTEM_DATA."
            ),
            details={
                "SYSTEM.PATHS.SYSTEM_DATA": resolved_system_data,
                "violations": violations,
            },
            operation="config.validate_state_path_layout",
        )


async def build_configuration_foundation(
    *,
    environment: ApplicationEnvironment,
    module_dependencies: ApplicationModuleDependencies,
    logging_instance: ApplicationLogging,
    edition_capabilities: EditionCapabilities,
) -> ConfigurationFoundation:
    configuration_data, degraded_mode = await load_configuration_data(
        environment=environment,
        module_dependencies=module_dependencies,
        logging_instance=logging_instance,
    )
    config = Config(
        configuration_data,
        main_app_base_dir=environment.base_dir,
    )
    _validate_state_path_layout(config=config)
    try:
        configure_dns_override_servers(_resolve_dns_override_servers(config))
    except ValueError as exception:
        log_handled_exception(
            logging_instance.logger,
            exception,
            message="Invalid SECURITY.DNS_OVERRIDE_SERVERS.",
            operation=OPERATION_DNS_OVERRIDE_SERVERS,
            level="error",
        )
        configure_dns_override_servers(None)
    runtime_flags_service = build_runtime_flags_service(
        config=config,
        edition_capabilities=edition_capabilities,
    )
    files = ConfigFilesPathResolver(config)
    return ConfigurationFoundation(
        config=config,
        files=files,
        runtime_flags_service=runtime_flags_service,
        configuration_data=configuration_data,
        degraded_mode=degraded_mode,
    )
