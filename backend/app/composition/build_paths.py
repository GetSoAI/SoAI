"""SoAI - Application path configuration assembly [backend/app/composition/build_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.application_dependencies import ApplicationEnvironment, ApplicationPaths
from app.composition.build_core_configuration import resolve_pid_file_path
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.plugins.protocols_instance import FilesProtocol

__all__ = (
    "build_application_paths",
    "resolve_backends_directory",
    "resolve_plugin_directory",
)


def resolve_plugin_directory(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
) -> str:
    plugins_path_value = config.get_str("PLUGINS.PATHS.PLUGINS")
    if plugins_path_value is None:
        raise StateError("PLUGINS.PATHS.PLUGINS resolved to None.")
    return files.resolve_path(plugins_path_value)


def resolve_backends_directory(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
) -> str:
    backends_path_value = config.get_str("PLUGINS.PATHS.BACKENDS")
    if backends_path_value is None:
        raise StateError("PLUGINS.PATHS.BACKENDS resolved to None.")
    return files.resolve_path(backends_path_value)


def build_application_paths(
    *,
    environment: ApplicationEnvironment,
    config: ConfigProtocol,
    files: FilesProtocol,
) -> ApplicationPaths:
    pid_file_path = resolve_pid_file_path(
        config=config,
        files=files,
    )
    plugin_directory = resolve_plugin_directory(
        config=config,
        files=files,
    )
    backends_directory = resolve_backends_directory(
        config=config,
        files=files,
    )
    return ApplicationPaths(
        base_dir=environment.base_dir,
        main_venv_dir=environment.main_venv_dir,
        config_path=environment.config_path,
        plugin_directory=plugin_directory,
        backends_directory=backends_directory,
        pid_file_path=pid_file_path,
    )
