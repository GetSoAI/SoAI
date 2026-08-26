"""SoAI - Plugin backend installation drift detection [backend/plugins/manager/backend_installation_drift.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_STOPPED,
    resolve_plugin_runtime_state_name,
)
from core.state.state_transition_sets import PLUGIN_MANAGER_TRANSIENT_STATES
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "compute_backend_installation_state_overrides",
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


def compute_backend_installation_state_overrides(
    manager: PluginManagerRuntimeProtocol,
    plugin_records: list[JSONDict],
) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for record in plugin_records:
        plugin_name_value = record.get("plugin_name")
        if not isinstance(plugin_name_value, str) or not plugin_name_value:
            continue
        plugin_name = plugin_name_value
        if not coerce_bool_with_recovery(
            record,
            "supports_backend_installation",
            logger=get_logger(LOGGER_NAME),
            operation="plugins.manager.backend_installation_drift.supports_backend_installation",
            default=False,
            recover_message="Failed to parse supports_backend_installation (non-critical).",
        ):
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
            overrides[plugin_name] = PLUGIN_STATE_BACKEND_NOT_INSTALLED
            continue
        if _is_probably_broken_venv(install_path):
            overrides[plugin_name] = PLUGIN_STATE_BACKEND_NOT_INSTALLED
    return overrides


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
        overrides = compute_backend_installation_state_overrides(manager, records)
        for plugin_name in overrides:
            try:
                await manager.transition_plugin_manager_state(
                    plugin_name,
                    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
                    f"Backend installation drift detected ({reason}).",
                    context=None,
                )
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
