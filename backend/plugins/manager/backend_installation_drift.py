"""SoAI - Plugin backend installation drift detection [backend/plugins/manager/backend_installation_drift.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.persistent_runtime_truth import get_plugin_status_payload
from core.runtime.soai_identifiers import create_system_id
from core.state.plugin_state_generation import read_plugin_state_generation
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_STOPPED,
    resolve_plugin_runtime_state_name,
)
from core.state.state_transition_sets import PLUGIN_MANAGER_TRANSIENT_STATES
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from plugins.artifact_paths import get_plugin_file_hash
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.loader.loading import load_and_announce_plugin
from plugins.loader.loading_policy import PluginLoadPolicy
from plugins.manager.capability_support import supports_plugin_capability_from_record
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.types.json import JSONDict

__all__ = (
    "find_backend_installation_drift_candidates",
    "request_backend_installation_drift_scan",
)

LOGGER_NAME = "SoAI.plugins.manager.backend_installation_drift"
OPERATION_PLUGINS_MANAGER_BACKEND_INSTALLATION_DRIFT_PERSIST_TRANSITION = (
    "plugins.manager.backend_installation_drift.persist_transition"
)
OPERATION_PLUGINS_MANAGER_BACKEND_INSTALLATION_DRIFT_REQUEST_BACKEND_INSTALLATION_DRIFT_SCAN = (
    "plugins.manager.backend_installation_drift.request_backend_installation_drift_scan"
)
OPERATION_PLUGINS_MANAGER_BACKEND_INSTALLATION_DRIFT_SCAN = (
    "plugins.manager.backend_installation_drift.scan"
)


_VENV_DIR_CANDIDATES: tuple[str, ...] = ("venv", ".venv")


def _resolve_install_path(manager: PluginManagerRuntimeProtocol, plugin_name: str) -> str | None:
    backends_directory = manager.paths.backends_directory
    if not isinstance(backends_directory, str) or not backends_directory:
        return None
    return os.path.join(backends_directory, plugin_name)


def _is_probably_broken_venv(install_path: str) -> bool:
    for venv_dir_name in _VENV_DIR_CANDIDATES:
        venv_dir = os.path.join(install_path, venv_dir_name)
        if not os.path.isdir(venv_dir):
            continue
        win_python = os.path.join(venv_dir, "Scripts", "python.exe")
        posix_python = os.path.join(venv_dir, "bin", "python")
        posix_python3 = os.path.join(venv_dir, "bin", "python3")
        if (
            os.path.isfile(win_python)
            or os.path.isfile(posix_python)
            or os.path.isfile(posix_python3)
        ):
            return False
        return True
    return False


def find_backend_installation_drift_candidates(
    manager: PluginManagerRuntimeProtocol,
    plugin_records: list[JSONDict],
) -> list[str]:
    candidates: list[str] = []
    for record in plugin_records:
        plugin_name_value = record.get("plugin_name")
        if not isinstance(plugin_name_value, str) or not plugin_name_value:
            continue
        plugin_name = plugin_name_value
        if not supports_plugin_capability_from_record(record, "SUPPORTS_BACKEND_INSTALLATION"):
            continue
        state_value = record.get("state")
        state = resolve_plugin_runtime_state_name(
            state_value if isinstance(state_value, str) else None,
        )
        if state is None:
            continue
        if state in {
            PLUGIN_STATE_BACKEND_NOT_INSTALLED,
            PLUGIN_STATE_NOT_DETECTED,
        }:
            continue
        if state in PLUGIN_MANAGER_TRANSIENT_STATES:
            continue
        if state not in {PLUGIN_STATE_STOPPED, PLUGIN_STATE_INSTALL_ERROR}:
            continue
        install_path = _resolve_install_path(manager, plugin_name)
        if install_path is None:
            continue
        if not os.path.isdir(install_path):
            candidates.append(plugin_name)
            continue
        if _is_probably_broken_venv(install_path):
            candidates.append(plugin_name)
    return candidates


async def request_backend_installation_drift_scan(
    manager: PluginManagerRuntimeProtocol,
    *,
    reason: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        config = manager.dependencies.core.config
        cooldown_sec = config.get_float("PLUGINS.PERFORMANCE.BACKEND_DRIFT_SCAN_COOLDOWN_SEC")
        now = time.monotonic()
        async with manager.state.lifecycle.backend_drift_scan_lock:
            task = manager.state.lifecycle.backend_drift_scan_task
            if task is not None and (not task.done()):
                return
            last_requested = manager.state.lifecycle.backend_drift_scan_last_requested_monotonic
            if cooldown_sec > 0 and last_requested > 0 and (now - last_requested) < cooldown_sec:
                return

            async def _runner() -> None:
                await _run_backend_installation_drift_scan(manager, reason=reason)

            manager.state.lifecycle.backend_drift_scan_last_requested_monotonic = now
            lifecycle = manager.dependencies.infrastructure.lifecycle
            manager.state.lifecycle.backend_drift_scan_task = (
                manager.dependencies.infrastructure.task_helpers.spawn_tracked_task(
                    _runner(),
                    logger=logger,
                    name="plugin-backend-installation-drift-scan",
                    cancellation_binder=lifecycle.cancellation_binder,
                    cancellation_id=create_system_id(
                        subsystem="plugin_manager_backend_installation_drift_scan",
                        owner="scan",
                        include_random_suffix=False,
                    ),
                    owner="plugin_manager_backend_installation_drift_scan",
                    finalizer_tracker=lifecycle.finalizer_tracker,
                )
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to schedule backend installation drift scan (non-critical).",
            operation=OPERATION_PLUGINS_MANAGER_BACKEND_INSTALLATION_DRIFT_REQUEST_BACKEND_INSTALLATION_DRIFT_SCAN,
            details={"reason": reason},
            level="debug",
        )


async def _run_backend_installation_drift_scan(
    manager: PluginManagerRuntimeProtocol,
    *,
    reason: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await manager.require_ready()
        records = await manager.dependencies.databases.plugins.get_all_listable_plugins()
        candidates = find_backend_installation_drift_candidates(manager, records)
        for plugin_name in candidates:
            try:
                async with plugin_lifecycle_advisory_lock(manager, plugin_name):
                    async with manager.lifecycle.bounded_plugin_lock_scope(
                        plugin_name, timeout_seconds=30
                    ) as lock_result:
                        if not lock_result.acquired:
                            continue
                        await _verify_backend_installation_drift(manager, plugin_name, reason)
            except ValidationError:
                continue
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to persist backend drift state transition (non-critical).",
                    operation=OPERATION_PLUGINS_MANAGER_BACKEND_INSTALLATION_DRIFT_PERSIST_TRANSITION,
                    details={"plugin_name": plugin_name, "reason": reason},
                    level="debug",
                )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Backend installation drift scan failed (non-critical).",
            operation=OPERATION_PLUGINS_MANAGER_BACKEND_INSTALLATION_DRIFT_SCAN,
            details={"reason": reason},
            level="debug",
        )


async def _verify_backend_installation_drift(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    reason: str,
) -> None:
    database = manager.dependencies.databases.plugins
    aggregator = manager.dependencies.infrastructure.state_aggregator
    record = await database.get_plugin_by_name(plugin_name)
    if record is None or not supports_plugin_capability_from_record(
        record, "SUPPORTS_BACKEND_INSTALLATION"
    ):
        return
    state_value = record.get("state")
    state = resolve_plugin_runtime_state_name(state_value if isinstance(state_value, str) else None)
    if state not in {PLUGIN_STATE_STOPPED, PLUGIN_STATE_INSTALL_ERROR}:
        return
    generation = read_plugin_state_generation(await aggregator.get_all_plugin_states(), plugin_name)
    if generation is None or generation.status != state:
        return
    package_hash = record.get("file_hash")
    if not isinstance(package_hash, str) or not package_hash:
        return
    instance = await manager.get_plugin_instance(plugin_name)
    owned_instance: PluginInstanceProtocol | None = None

    try:
        if instance is None:
            outcome = await load_and_announce_plugin(
                manager,
                plugin_name,
                policy=PluginLoadPolicy(
                    catalog_state=state,
                    initial_state=state,
                    announce=False,
                    publish_failure_state=False,
                ),
            )
            instance = outcome.instance
            owned_instance = outcome.acquired_instance
        else:
            async with manager.state.locks.load_lock:
                surface = manager.state.catalog.loaded_plugin_surfaces.get(plugin_name)
                if surface is None or surface[1] != package_hash:
                    return
        async with asyncio.timeout(LOCAL_IO_TIMEOUT_SEC):
            status = await get_plugin_status_payload(
                instance,
                operation=OPERATION_PLUGINS_MANAGER_BACKEND_INSTALLATION_DRIFT_SCAN,
                logger=manager.logger,
                raise_on_error=True,
            )
        if status.get("installed") is not False or status.get("error") is not None:
            return
        if await get_plugin_file_hash(manager, plugin_name) != package_hash:
            return
        current_record = await database.get_plugin_by_name(plugin_name)
        current_generation = read_plugin_state_generation(
            await aggregator.get_all_plugin_states(), plugin_name
        )
        if current_record is None or not supports_plugin_capability_from_record(
            current_record, "SUPPORTS_BACKEND_INSTALLATION"
        ):
            return
        if (
            current_record.get("state") != state
            or current_record.get("file_hash") != package_hash
            or current_generation != generation
        ):
            return
        await manager.transition_plugin_manager_state(
            plugin_name,
            PLUGIN_STATE_BACKEND_NOT_INSTALLED,
            f"Backend installation drift detected ({reason}).",
            context=None,
        )
    finally:
        if owned_instance is not None:
            await uncancel_then_cleanup(
                manager.release_discovery_plugin_instance(
                    plugin_name, expected_instance=owned_instance
                )
            )
