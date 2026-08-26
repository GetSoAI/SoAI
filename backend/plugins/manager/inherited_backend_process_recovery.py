"""SoAI - Recovery of plugin backend descendants carrying inherited ownership [backend/plugins/manager/inherited_backend_process_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import psutil

from core.errors.exceptions import ValidationError
from core.runtime.backend_process_tracking import (
    BackendProcessIdentity,
    backend_process_identities_match,
)
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.serialization.json_parsing import parse_json_dict

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = ("reconcile_inherited_backend_processes",)

PLUGIN_WORKER_BOOTSTRAP_ENV = "SOAI_PLUGIN_WORKER_BOOTSTRAP"


async def reconcile_inherited_backend_processes(
    manager: PluginManagerLifecycleTarget,
    *,
    logger: LoggerProtocol,
) -> int:
    owned_pids = _discover_inherited_backend_pids(
        backends_directory=manager.paths.backends_directory,
        logger=logger,
    )
    reconciled_count = 0
    for plugin_name, discovered in owned_pids.items():
        record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        if not (record and record.get("supports_backend_process_tracking")):
            continue
        existing = await manager.dependencies.databases.plugins.get_runtime_processes(plugin_name)
        merged = _merge_backend_process_identities(existing, discovered)
        if not backend_process_identities_match(existing, merged):
            await manager.dependencies.databases.plugins.set_runtime_processes(
                plugin_name,
                merged,
            )
        reconciled_count += len(discovered)
    return reconciled_count


def _discover_inherited_backend_pids(
    *,
    backends_directory: str,
    logger: LoggerProtocol,
) -> dict[str, list[BackendProcessIdentity]]:
    owned_processes: dict[str, list[BackendProcessIdentity]] = {}
    try:
        processes = psutil.process_iter(["pid", "cmdline", "exe"])
        for process in processes:
            owned_process = _resolve_owned_backend_process(
                process,
                backends_directory=backends_directory,
            )
            if owned_process is None:
                continue
            plugin_name, identity = owned_process
            if plugin_name not in owned_processes:
                owned_processes[plugin_name] = []
            owned_processes[plugin_name].append(identity)
    except psutil.Error as exception:
        logger.warning(
            "Plugin backend ownership scan failed: %s",
            f"{type(exception).__name__}: {exception}",
        )
    return owned_processes


def _resolve_owned_backend_process(
    process: psutil.Process,
    *,
    backends_directory: str,
) -> tuple[str, BackendProcessIdentity] | None:
    try:
        create_time_ms = read_process_create_time_ms(process)
        bootstrap_text = process.environ().get(PLUGIN_WORKER_BOOTSTRAP_ENV, "")
        if not bootstrap_text:
            return None
        bootstrap = parse_json_dict(bootstrap_text, field=PLUGIN_WORKER_BOOTSTRAP_ENV)
        plugin_name_value = bootstrap.get("plugin_name")
        install_path_value = bootstrap.get("install_path")
        if not isinstance(plugin_name_value, str) or not plugin_name_value.strip():
            return None
        if not isinstance(install_path_value, str) or not install_path_value.strip():
            return None
        plugin_name = plugin_name_value.strip()
        expected_install_path = os.path.realpath(os.path.join(backends_directory, plugin_name))
        marker_install_path = os.path.realpath(install_path_value)
        if marker_install_path != expected_install_path:
            return None
        executable = process.exe()
        command_line = tuple(process.cmdline())
        if not _process_executes_under_install_path(
            executable=executable,
            command_line=command_line,
            install_path=expected_install_path,
        ):
            return None
        if read_process_create_time_ms(process) != create_time_ms:
            return None
        return (plugin_name, {"pid": int(process.pid), "createTimeMs": create_time_ms})
    except (OSError, ValidationError, psutil.Error):
        return None


def _process_executes_under_install_path(
    *,
    executable: str,
    command_line: tuple[str, ...],
    install_path: str,
) -> bool:
    candidates = (executable, *command_line[:2])
    for candidate in candidates:
        if not candidate or not os.path.isabs(candidate):
            continue
        resolved_candidate = os.path.realpath(candidate)
        try:
            if os.path.commonpath((install_path, resolved_candidate)) == install_path:
                return True
        except ValueError:
            continue
    return False


def _merge_backend_process_identities(
    existing: list[BackendProcessIdentity],
    discovered: list[BackendProcessIdentity],
) -> list[BackendProcessIdentity]:
    merged: dict[tuple[int, int], BackendProcessIdentity] = {}
    for identity in (*existing, *discovered):
        merged[(identity["pid"], identity["createTimeMs"])] = identity
    return [merged[key] for key in sorted(merged)]
