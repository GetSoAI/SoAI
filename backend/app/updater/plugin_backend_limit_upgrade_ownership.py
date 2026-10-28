"""SoAI - Offline plugin upgrade ownership and retained package coverage [backend/app/updater/plugin_backend_limit_upgrade_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING

import psutil

from app.installation_transaction_admission import reject_unfinished_installation_transactions
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.update_lock import (
    require_software_update_lock_owner,
    resolve_software_update_lock_dir,
)
from core.bootstrap.install_locks import (
    acquire_lock_dir,
    inherited_install_lock_is_valid,
    lock_dir_has_live_owner,
    read_lock_pid,
    release_lock_dir,
)
from core.bootstrap.lock import (
    INSTALLATION_TRANSACTION_LOCK_FILENAME,
    acquire_interprocess_lock,
    require_no_foreign_install_lock,
)
from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.errors.exceptions import StateError
from core.files.path_policy import is_path_within_base
from core.meta.paths import join_data_abs
from core.runtime.instance_record import read_verified_runtime_instance_record

if TYPE_CHECKING:
    from app.updater.software_update.activation_identity import UpdateActivationIdentity
    from core.logging.protocols import LoggerProtocol

__all__ = ("guard_plugin_upgrade_ownership", "retained_plugin_sources")


@contextmanager
def guard_plugin_upgrade_ownership(
    base_path: str, *, edition: str, logger: LoggerProtocol
) -> Generator[None]:
    install_lock_path = join_data_abs(base_path, "state", "locks", "soai.install.lock.d")
    update_lock_path = resolve_software_update_lock_dir(base_path)
    ancestors = {process.pid for process in psutil.Process().parents()}
    inherited_install = inherited_install_lock_is_valid(install_lock_path)
    require_no_foreign_install_lock(
        base_path, inherited_install_lock_validator=inherited_install_lock_is_valid
    )
    update_owner = read_lock_pid(update_lock_path)
    if os.path.lexists(update_lock_path):
        if update_owner is None or update_owner not in ancestors:
            raise StateError("A plugin upgrade requires verified updater ownership.")
        require_software_update_lock_owner(
            update_lock_path, base_path=base_path, edition=edition, expected_pid=update_owner
        )
    with ExitStack() as ownership:
        if os.name != "nt" or not inherited_install:
            ownership.enter_context(
                acquire_interprocess_lock(
                    join_data_abs(base_path, "locks", INSTALLATION_TRANSACTION_LOCK_FILENAME),
                    timeout_sec=30,
                )
            )
        require_no_foreign_install_lock(
            base_path, inherited_install_lock_validator=inherited_install_lock_is_valid
        )
        runtime_lock_path = join_data_abs(base_path, "state", "locks", "soai.runtime.lock.d")
        if (
            lock_dir_has_live_owner(runtime_lock_path)
            or read_verified_runtime_instance_record(
                resolve_runtime_record_path(base_path, logger=logger),
                base_dir=base_path,
                expected_edition=edition,
            )
            is not None
        ):
            raise StateError("Plugin configuration upgrades require a stopped installation.")
        runtime_lock = acquire_lock_dir(runtime_lock_path, timeout_seconds=30)
        ownership.callback(release_lock_dir, runtime_lock)
        if (
            read_verified_runtime_instance_record(
                resolve_runtime_record_path(base_path, logger=logger),
                base_dir=base_path,
                expected_edition=edition,
            )
            is not None
        ):
            raise StateError("SoAI started while plugin upgrade ownership was being acquired.")
        yield


def retained_plugin_sources(
    prepared_update: UpdateActivationIdentity | None,
    *,
    base_path: str,
    directories: tuple[str, ...],
    edition: str,
) -> dict[str, str] | None:
    if prepared_update is None:
        reject_unfinished_installation_transactions(base_path)
        return None
    if prepared_update.edition != edition:
        raise StateError("Plugin upgrade edition does not match its protected transaction.")
    inventory = require_rollback_inventory(prepared_update.paths, old_complete=True)
    if inventory is None:
        raise StateError("Plugin upgrade has no validated original package inventory.")
    sources: dict[str, str] = {}
    internal = os.path.join(base_path, "plugins")
    for directory in directories:
        if os.path.normcase(directory) == os.path.normcase(internal):
            if "plugins" not in inventory.replacement_roots:
                raise StateError("Internal plugin storage is outside update rollback coverage.")
            sources[directory] = os.path.join(prepared_update.paths.rollback_old_path, "plugins")
            continue
        matches = [
            (slot, destination)
            for slot, destination in inventory.persisted_state.destinations.items()
            if destination in inventory.persisted_state.directory_destinations
            and is_path_within_base(destination, directory)
        ]
        if len(matches) != 1:
            raise StateError("Configured plugin storage is outside update rollback coverage.")
        slot, destination = matches[0]
        sources[directory] = os.path.normpath(
            os.path.join(
                prepared_update.paths.rollback_old_path,
                *slot.split("/"),
                os.path.relpath(directory, destination),
            )
        )
    return sources
