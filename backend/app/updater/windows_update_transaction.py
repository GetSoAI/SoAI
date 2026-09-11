"""SoAI - Windows installer participation in retained update transactions [backend/app/updater/windows_update_transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core_edition import build_core_edition_composition
from app.dependencies import build_updater_module_dependencies
from app.updater.disk_space import require_disk_space_for_update
from app.updater.service_config_loading import read_updater_config
from app.updater.software_update.activation_state import (
    activation_commit_lock_path,
    persist_failed_activation_result,
    prepare_update_activation,
    read_pending_update_activation,
    read_update_activation_identity,
    require_update_candidate_stopped,
    validate_update_recovery_evidence,
)
from app.updater.software_update.activation_supervision import (
    start_update_activation,
    wait_for_update_activation,
)
from app.updater.software_update.install_transaction_inventory import (
    plan_replacement_roots,
    prepare_update_rollback,
    require_rollback_inventory,
)
from app.updater.software_update.install_transaction_persisted_state import (
    plan_persisted_update_state,
    resolve_update_plugins_path,
    resolve_update_state_files,
)
from app.updater.software_update.install_transaction_state import (
    ACTIVATION_FAILED_MARKER,
    MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    MANAGED_VENDOR_RELATIVE_COMPONENTS,
    NEW_COMPLETE_MARKER,
    OLD_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    AppliedUpdateTransaction,
    UpdateTransactionPaths,
    marker_path,
    paths_from_transaction_directory,
    validate_transaction_markers,
    write_marker,
)
from app.updater.software_update.install_transaction_state_transfer import (
    install_persisted_update_directories,
)
from app.updater.software_update.plugin_reconciliation import (
    plan_plugin_reconciliation,
    reconcile_staged_plugins,
    stage_configured_plugins,
)
from app.updater.target_runtime_preparation import prepare_target_update_runtime
from app.updater.windows_installer_preparation import PreparedWindowsInstaller
from core.bootstrap.install_payload import managed_root_entries
from core.bootstrap.install_payload_transaction import (
    copy_install_entry,
    install_entry_copy_size,
    replace_install_entry,
)
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.venv_paths import get_venv_path
from core.errors.exceptions import StateError
from core.files.path_policy import is_path_within_base, safe_join_relative_under_base
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC

if TYPE_CHECKING:
    from app.updater.release_bundle import PreparedReleaseBundle
    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "prepare_windows_update_transaction",
    "finish_windows_update_transaction",
    "activate_windows_update_transaction",
    "publish_windows_update_failure",
)

LOGGER_NAME = "SoAI.app.updater.windows_update_transaction"
CONFIGURED_PLUGIN_STAGE = "configured_plugins"


def publish_windows_update_failure(base_path: str, transaction_path: str, task_id: str) -> None:
    paths = paths_from_transaction_directory(base_path, transaction_path)
    with acquire_interprocess_lock(
        activation_commit_lock_path(paths.base_path), timeout_sec=CONTROL_TIMEOUT_SEC
    ):
        validate_update_recovery_evidence(paths)
        if read_update_activation_identity(paths).task_id != task_id:
            raise StateError("Windows failure does not identify the accepted update task.")
        if os.path.exists(marker_path(paths.transaction_path, SUCCESS_COMPLETE_MARKER)):
            raise StateError("A committed Windows update cannot publish a failure result.")
        require_update_candidate_stopped(paths)
        if read_pending_update_activation(paths) is not None:
            write_marker(paths.transaction_path, ACTIVATION_FAILED_MARKER)
        persist_failed_activation_result(paths)


def activate_windows_update_transaction(
    base_path: str, transaction_path: str, task_id: str
) -> bool:
    paths = paths_from_transaction_directory(base_path, transaction_path)
    pending = read_pending_update_activation(paths)
    updater = build_core_edition_composition().updater
    if pending is None or pending.task_id != task_id or pending.edition != updater.edition:
        raise StateError("Windows startup does not match its accepted update identity.")
    logger = get_logger(LOGGER_NAME)
    candidate = start_update_activation(
        pending,
        platform_name="Windows",
        main_py_path=os.path.join(paths.base_path, updater.entrypoint_relative_path),
        logger=logger,
    )
    return wait_for_update_activation(candidate, logger=logger)


def prepare_windows_update_transaction(
    *,
    paths: UpdateTransactionPaths,
    prepared: PreparedWindowsInstaller,
    release_bundle: PreparedReleaseBundle,
    config: ConfigProtocol,
    config_path: str,
    task_id: str,
    from_version: str,
    reservation_provider: StorageManagerProtocol,
    before_handoff: Callable[[], bool],
) -> bool:
    edition = release_bundle.updater.edition
    identity = read_update_activation_identity(paths)
    if (
        identity.task_id != task_id
        or identity.edition != edition
        or identity.from_version != from_version
        or identity.to_version != release_bundle.manifest.version
        or os.path.normcase(identity.config_path) != os.path.normcase(os.path.abspath(config_path))
    ):
        raise StateError(
            "Windows snapshot preparation does not match its accepted update identity."
        )
    payload_bytes = install_entry_copy_size(prepared.staged_root)
    with reservation_provider.reserve_disk_space(
        path=paths.staged_new_path,
        required_bytes=payload_bytes,
        operation="application_updater.windows_payload_retention",
        details={},
    ) as reservation:
        with reservation.claim_write_bytes(payload_bytes) as claim:
            for name in os.listdir(prepared.staged_root):
                copy_install_entry(os.path.join(prepared.staged_root, name), paths.staged_new_path)
            claim.commit()
    additional_roots = tuple(
        sorted(
            {
                os.path.relpath(path, paths.base_path).split(os.sep, maxsplit=1)[0]
                for path in (*prepared.state_files, *prepared.state_directories)
            }.intersection(managed_root_entries(edition))
        )
    )
    roots = plan_replacement_roots(paths, edition, additional_roots)
    covered = (
        *(os.path.join(paths.base_path, name) for name in roots),
        *(
            os.path.join(paths.base_path, *components)
            for components in (
                MANAGED_VENDOR_RELATIVE_COMPONENTS,
                MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
                MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
            )
        ),
    )
    native_files = tuple(
        path
        for path in prepared.state_files
        if not any(is_path_within_base(root, path) for root in covered)
    )
    native_directories = tuple(
        path
        for path in prepared.state_directories
        if not any(is_path_within_base(root, path) for root in covered)
    )
    plugins_path = resolve_update_plugins_path(config)
    default_plugins = os.path.join(paths.base_path, "plugins")
    external_plugins = os.path.normcase(plugins_path) != os.path.normcase(default_plugins)
    state_files = (*resolve_update_state_files(config, config_path), *native_files)
    state_directories = (
        *native_directories,
        get_venv_path(paths.base_path),
        *((plugins_path,) if external_plugins else ()),
    )
    state = plan_persisted_update_state(paths, roots, state_files, state_directories)
    if external_plugins and plugins_path not in state.directory_destinations:
        raise StateError("Configured plugin storage overlaps native runtime recovery storage.")
    bundled_plugins = os.path.join(paths.staged_new_path, "plugins")
    for installed_plugins in (
        (default_plugins, plugins_path) if external_plugins else (default_plugins,)
    ):
        plan_plugin_reconciliation(
            installed_plugins=installed_plugins,
            staged_plugins=bundled_plugins,
            target_version=release_bundle.manifest.core_version,
        )
    snapshot_bytes = sum(
        install_entry_copy_size(path)
        for path in (*covered, *state.destinations.values())
        if os.path.lexists(path)
    )
    require_disk_space_for_update(paths.base_path, snapshot_bytes + payload_bytes, 0)
    if not before_handoff():
        return False
    if external_plugins:
        stage_configured_plugins(
            installed_plugins=plugins_path,
            bundled_plugins=bundled_plugins,
            staging_parent=os.path.join(paths.transaction_path, CONFIGURED_PLUGIN_STAGE),
            target_version=release_bundle.manifest.core_version,
            reservation_provider=reservation_provider,
        )
    reconcile_staged_plugins(
        installed_plugins=default_plugins,
        staged_plugins=bundled_plugins,
        target_version=release_bundle.manifest.core_version,
        reservation_provider=reservation_provider,
    )
    prepare_update_rollback(
        paths,
        edition=edition,
        state_files=state_files,
        state_directories=state_directories,
        additional_roots=additional_roots,
    )
    return True


def finish_windows_update_transaction(base_path: str, transaction_path: str, task_id: str) -> None:
    base_path = os.path.abspath(base_path)
    transaction_path = safe_join_relative_under_base(
        base_path=base_path,
        relative_path=os.path.relpath(transaction_path, base_path),
        description="Windows update transaction",
        error_cls=StateError,
    )
    paths = paths_from_transaction_directory(base_path, transaction_path)
    identity = read_update_activation_identity(paths)
    updater = build_core_edition_composition().updater
    if (
        identity.task_id != task_id
        or identity.edition != updater.edition
        or (identity.to_version != updater.core_version)
    ):
        raise StateError("Windows installation does not match its accepted update identity.")
    validate_transaction_markers(paths.transaction_path)
    if not all(
        os.path.isfile(marker_path(paths.transaction_path, marker))
        for marker in (
            OLD_COMPLETE_MARKER,
            ROLLBACK_REQUIRED_MARKER,
        )
    ) or os.path.lexists(marker_path(paths.transaction_path, NEW_COMPLETE_MARKER)):
        raise StateError("Windows installer completion has an invalid transaction phase.")
    inventory = require_rollback_inventory(paths, old_complete=True)
    if inventory is None:
        raise StateError("Windows installation has no retained rollback inventory.")
    read_ok, configured_base, config = read_updater_config(
        config_path=identity.config_path,
        module_dependencies=build_updater_module_dependencies(),
    )
    if (
        not read_ok
        or config is None
        or os.path.normcase(configured_base) != os.path.normcase(base_path)
    ):
        raise StateError("Windows update configuration could not be loaded for activation.")
    plugins_path = resolve_update_plugins_path(config)
    if os.path.normcase(plugins_path) != os.path.normcase(os.path.join(base_path, "plugins")):
        staged_plugins = os.path.join(
            paths.transaction_path, CONFIGURED_PLUGIN_STAGE, os.path.basename(plugins_path)
        )
        install_persisted_update_directories(
            paths,
            inventory.persisted_state,
            {plugins_path: staged_plugins},
        )
    replace_install_entry(
        os.path.join(paths.staged_new_path, "plugins"),
        base_path,
        staging_root=paths.transaction_path,
    )
    logger = get_logger(LOGGER_NAME)
    if not prepare_target_update_runtime(
        base_path=base_path,
        config_path=identity.config_path,
        config=config,
        updater=updater,
        logger=logger,
    ):
        raise StateError("Windows target dependency or migration preparation failed.")
    write_marker(paths.transaction_path, NEW_COMPLETE_MARKER)
    prepare_update_activation(AppliedUpdateTransaction(base_path, paths.transaction_path))
