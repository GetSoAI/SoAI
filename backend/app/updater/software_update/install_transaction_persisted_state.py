"""SoAI - Configured persisted files in update transactions [backend/app/updater/software_update/install_transaction_persisted_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.restore_destinations import ensure_restore_destination_is_safe
from app.installation_transaction_admission import (
    TRANSACTION_CLEANUP_PREFIX,
    TRANSACTION_PREFIX,
)
from app.updater.software_update.install_transaction_state import (
    MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    MANAGED_VENDOR_RELATIVE_COMPONENTS,
    UpdateTransactionPaths,
)
from core.config.path_resolution import resolve_default_config_schema_path
from core.errors.exceptions import StateError
from core.files.path_policy import is_path_within_base
from core.types.json import is_str_list

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = (
    "PERSISTED_STATE_DIRECTORY",
    "PersistedUpdateState",
    "persisted_directory_staging",
    "plan_persisted_update_state",
    "read_persisted_update_state",
    "resolve_update_state_files",
    "resolve_update_plugins_path",
)

PERSISTED_STATE_DIRECTORY = "persisted"


@dataclass(frozen=True, slots=True)
class PersistedUpdateState:
    destinations: dict[str, str]
    original_entries: tuple[str, ...]
    directory_destinations: tuple[str, ...]
    absent_parents: tuple[str, ...]


def resolve_update_plugins_path(config: ConfigProtocol) -> str:
    plugins_path = config.get_str("PLUGINS.PATHS.PLUGINS")
    if not plugins_path:
        raise StateError("The configured plugin directory is required for update preservation.")
    for key in ("MODELS.MANAGER.PATHS.MODELS", "DATA.FILES.PATHS.FILES_STORAGE"):
        preserved_path = config.get_str(key)
        if preserved_path and is_path_within_base(plugins_path, preserved_path):
            raise StateError(
                "Configured plugin storage contains a model or user-file store; separate their paths before updating."
            )
    return plugins_path


def resolve_update_state_files(config: ConfigProtocol, config_path: str) -> tuple[str, ...]:
    database_path = config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB")
    if not database_path:
        raise StateError("The configured database path is required for update rollback.")
    configuration_files: list[str] = []
    for key in ("SYSTEM.PATHS.SYSTEM_ENCRYPTION_KEY", "SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH"):
        configured_path = config.get_str(key)
        if not configured_path:
            raise StateError(f"The configured state path {key} is required for update rollback.")
        configuration_files.append(configured_path)
    return (
        config_path,
        f"{config_path}.backup",
        resolve_default_config_schema_path(config_path),
        *(f"{database_path}{suffix}" for suffix in ("", "-wal", "-shm", "-journal")),
        *configuration_files,
    )


def _require_state_destination(
    paths: UpdateTransactionPaths,
    replacement_roots: tuple[str, ...],
    destination: str,
    *,
    require_existing_file: bool = True,
    require_existing_directory: bool = False,
) -> None:
    ensure_restore_destination_is_safe(destination)
    if destination != os.path.abspath(destination):
        raise StateError("Update state destinations must use normalized absolute paths.")
    protected_paths = (
        paths.transaction_path,
        *(os.path.join(paths.base_path, name) for name in replacement_roots),
        os.path.join(paths.base_path, *MANAGED_VENDOR_RELATIVE_COMPONENTS),
    )
    for protected in protected_paths:
        try:
            common = os.path.commonpath(
                (os.path.normcase(destination), os.path.normcase(protected))
            )
        except ValueError:
            continue
        if common in {os.path.normcase(destination), os.path.normcase(protected)}:
            raise StateError("Configured update state overlaps release or recovery storage.")
    if require_existing_file and os.path.lexists(destination) and not os.path.isfile(destination):
        raise StateError("Configured update state must be a regular file.")
    if (
        require_existing_directory
        and os.path.lexists(destination)
        and not os.path.isdir(destination)
    ):
        raise StateError("Configured update runtime must be a regular directory.")
    if any(
        component.startswith((TRANSACTION_PREFIX, TRANSACTION_CLEANUP_PREFIX))
        for component in destination.split(os.sep)
    ):
        raise StateError("Configured update state overlaps update recovery storage.")
    existing_parent = os.path.dirname(destination)
    while not os.path.lexists(existing_parent):
        existing_parent = os.path.dirname(existing_parent)
    if not os.path.isdir(existing_parent):
        raise StateError("Configured update state has a non-directory parent.")


def persisted_directory_staging(paths: UpdateTransactionPaths, slot: str, destination: str) -> str:
    staging_name = f".soai_restore_{os.path.basename(paths.transaction_path)}_{slot.split('/')[1]}"
    staging = os.path.join(os.path.dirname(destination), staging_name)
    ensure_restore_destination_is_safe(staging)
    return staging


def plan_persisted_update_state(
    paths: UpdateTransactionPaths,
    replacement_roots: tuple[str, ...],
    state_files: tuple[str, ...],
    state_directories: tuple[str, ...] = (),
) -> PersistedUpdateState:
    managed_files = {
        os.path.normcase(os.path.join(paths.base_path, *components))
        for components in (
            MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
            MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
        )
    }
    destinations: dict[str, str] = {}
    seen: set[str] = set()
    original_entries: list[str] = []
    absent_parents: set[str] = set()
    for destination in state_files:
        _require_state_destination(paths, replacement_roots, destination)
    for destination in state_directories:
        _require_state_destination(
            paths,
            replacement_roots,
            destination,
            require_existing_file=False,
            require_existing_directory=True,
        )
    directories = tuple(sorted(set(state_directories)))
    directories = tuple(
        directory
        for directory in directories
        if not any(
            os.path.normcase(directory).startswith(os.path.normcase(parent) + os.sep)
            for parent in directories
            if parent != directory
        )
    )
    selected_paths = (
        *directories,
        *(
            file
            for file in state_files
            if not any(
                os.path.normcase(file).startswith(os.path.normcase(directory) + os.sep)
                for directory in directories
            )
        ),
    )
    for destination in selected_paths:
        normalized = os.path.normcase(destination)
        if normalized in managed_files or normalized in seen:
            continue
        seen.add(normalized)
        slot = (
            f"{PERSISTED_STATE_DIRECTORY}/{len(destinations):08d}/{os.path.basename(destination)}"
        )
        destinations[slot] = destination
        if destination in directories and os.path.lexists(
            persisted_directory_staging(paths, slot, destination)
        ):
            raise StateError(
                "Update directory restoration staging already exists; preserve it for repair."
            )
        if os.path.lexists(destination):
            original_entries.append(slot)
        parent = os.path.dirname(destination)
        while not os.path.lexists(parent):
            absent_parents.add(parent)
            parent = os.path.dirname(parent)
    return PersistedUpdateState(
        destinations, tuple(original_entries), directories, tuple(sorted(absent_parents))
    )


def read_persisted_update_state(
    payload: JSONDict,
    paths: UpdateTransactionPaths,
    replacement_roots: tuple[str, ...],
    original_entries: list[str],
) -> PersistedUpdateState:
    raw_destinations = payload.get("persisted_destinations")
    absent_parents = payload.get("persisted_absent_parents")
    directories = payload.get("persisted_directories")
    if (
        not isinstance(raw_destinations, dict)
        or not is_str_list(absent_parents)
        or not is_str_list(directories)
    ):
        raise StateError("Update persisted-state inventory is invalid.")
    destinations: dict[str, str] = {}
    for slot, destination in raw_destinations.items():
        if not isinstance(destination, str):
            raise StateError("Update persisted-state destination is invalid.")
        _require_state_destination(
            paths, replacement_roots, destination, require_existing_file=False
        )
        expected = (
            f"{PERSISTED_STATE_DIRECTORY}/{len(destinations):08d}/{os.path.basename(destination)}"
        )
        if slot != expected:
            raise StateError("Update persisted-state slot is invalid.")
        destinations[slot] = destination
    if len({os.path.normcase(path) for path in destinations.values()}) != len(destinations):
        raise StateError("Update persisted-state destinations are duplicated.")
    if len(set(directories)) != len(directories) or any(
        directory not in destinations.values() for directory in directories
    ):
        raise StateError("Update directory inventory does not match selected destinations.")
    if any(
        os.path.normcase(destination).startswith(os.path.normcase(directory) + os.sep)
        for destination in destinations.values()
        for directory in directories
        if destination != directory
    ):
        raise StateError("Update state destinations overlap.")
    if len(set(absent_parents)) != len(absent_parents):
        raise StateError("Update persisted-state parent inventory is duplicated.")
    for parent in absent_parents:
        ensure_restore_destination_is_safe(parent)
        if parent != os.path.abspath(parent) or not any(
            destination.startswith(parent + os.sep) for destination in destinations.values()
        ):
            raise StateError("Update persisted-state parent is unrelated to its files.")
    originals = tuple(slot for slot in destinations if slot in original_entries)
    return PersistedUpdateState(destinations, originals, tuple(directories), tuple(absent_parents))
