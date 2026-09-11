"""SoAI - Durable update replacement inventory [backend/app/updater/software_update/install_transaction_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.updater.disk_space import require_disk_space_for_update
from app.updater.software_update.install_transaction_managed_data import (
    copy_managed_data_to_rollback,
    prepare_managed_data_commit,
)
from app.updater.software_update.install_transaction_persisted_state import (
    PersistedUpdateState,
    plan_persisted_update_state,
    read_persisted_update_state,
)
from app.updater.software_update.install_transaction_state import (
    MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    MANAGED_ROLLBACK_DIR,
    MANAGED_VENDOR_RELATIVE_COMPONENTS,
    OLD_COMPLETE_MARKER,
    PREPARING_MARKER,
    ROLLBACK_INVENTORY_REQUIRED_MARKER,
    UpdateTransactionPaths,
    marker_path,
    write_marker,
)
from app.updater.software_update.install_transaction_state_transfer import (
    copy_persisted_update_state,
)
from core.bootstrap.install_payload import managed_root_entries
from core.bootstrap.install_payload_transaction import copy_install_entry, install_entry_copy_size
from core.bootstrap.venv_paths import get_venv_path
from core.errors.exceptions import StateError
from core.files.path_policy import (
    safe_join_relative_under_base,
    safe_join_relative_under_base_lexical,
)
from core.files.staged_transfer import compute_file_sha256
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import atomic_write_json_content
from core.filesystem.file_sync import fsync_install_entry
from core.filesystem.open_files import read_regular_file_no_symlink
from core.filesystem.path_coercion import normalize_filesystem_path
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.types.json import is_str_list

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "plan_replacement_roots",
    "prepare_update_rollback",
    "require_rollback_inventory",
    "write_rollback_inventory",
)

ROLLBACK_INVENTORY_FILENAME = "rollback_inventory.json"


@dataclass(frozen=True, slots=True)
class UpdateRollbackInventory:
    replacement_roots: tuple[str, ...]
    persisted_state: PersistedUpdateState
    runtime_directory: str | None


def _installed_original_path(
    paths: UpdateTransactionPaths, entry: str, state: PersistedUpdateState
) -> str:
    if entry in state.destinations:
        return state.destinations[entry]
    return os.path.join(paths.base_path, *entry.removeprefix(f"{MANAGED_ROLLBACK_DIR}/").split("/"))


def _original_fingerprint(path: str) -> str:
    entries: JSONDict = {}
    pending = [(normalize_filesystem_path(path), "")]
    while pending:
        entry_path, relative_path = pending.pop()
        metadata = os.lstat(entry_path)
        if stat.S_ISLNK(metadata.st_mode):
            entries[relative_path] = f"symlink:{os.readlink(entry_path)}"
        elif stat.S_ISREG(metadata.st_mode):
            digest = compute_file_sha256(entry_path).sha256_hex
            entries[relative_path] = f"file:{stat.S_IMODE(metadata.st_mode)}:{digest}"
        elif stat.S_ISDIR(metadata.st_mode):
            entries[relative_path] = f"directory:{stat.S_IMODE(metadata.st_mode)}"
            for name in os.listdir(entry_path):
                pending.append((os.path.join(entry_path, name), f"{relative_path}/{name}"))
        else:
            raise StateError("Update originals contain an unsupported filesystem entry.")
    return hashlib.sha256(serialize_json_compact_stable_strict(entries).encode("utf-8")).hexdigest()


def plan_replacement_roots(
    paths: UpdateTransactionPaths, edition: str, additional_roots: tuple[str, ...] = ()
) -> tuple[str, ...]:
    staged_roots = {name for name in os.listdir(paths.staged_new_path) if name != "data"}
    roots = tuple(sorted(staged_roots.union(additional_roots)))
    owned_roots = managed_root_entries(edition)
    if any(name not in owned_roots for name in roots):
        raise StateError("Update payload contains content outside release ownership.")
    return roots


def write_rollback_inventory(
    paths: UpdateTransactionPaths,
    replacement_roots: tuple[str, ...],
    state_files: tuple[str, ...] = (),
    state_directories: tuple[str, ...] = (),
) -> PersistedUpdateState:
    state = plan_persisted_update_state(paths, replacement_roots, state_files, state_directories)
    entries = [
        name for name in replacement_roots if os.path.lexists(os.path.join(paths.base_path, name))
    ]
    for components in (
        MANAGED_VENDOR_RELATIVE_COMPONENTS,
        MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
        MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    ):
        if os.path.lexists(os.path.join(paths.base_path, *components)):
            entries.append("/".join((MANAGED_ROLLBACK_DIR, *components)))
    entries.extend(state.original_entries)
    rollback_copy_bytes = sum(
        install_entry_copy_size(_installed_original_path(paths, entry, state)) for entry in entries
    )
    require_disk_space_for_update(
        paths.base_path,
        rollback_copy_bytes + install_entry_copy_size(paths.staged_new_path),
        0,
        operation="application_updater.rollback_copy_space",
    )
    original_hashes = {
        entry: _original_fingerprint(_installed_original_path(paths, entry, state))
        for entry in entries
    }
    atomic_write_json_content(
        os.path.join(paths.transaction_path, ROLLBACK_INVENTORY_FILENAME),
        {
            "paths": sorted(entries),
            "replacement_roots": list(replacement_roots),
            "original_hashes": original_hashes,
            "persisted_destinations": dict(state.destinations),
            "persisted_absent_parents": list(state.absent_parents),
            "persisted_directories": list(state.directory_destinations),
            "runtime_directory": (
                get_venv_path(paths.base_path)
                if get_venv_path(paths.base_path) in state.directory_destinations
                else None
            ),
        },
        fsync_parent_directory=True,
    )
    write_marker(paths.transaction_path, ROLLBACK_INVENTORY_REQUIRED_MARKER)
    return state


def prepare_update_rollback(
    paths: UpdateTransactionPaths,
    *,
    edition: str,
    state_files: tuple[str, ...] = (),
    state_directories: tuple[str, ...] = (),
    additional_roots: tuple[str, ...] = (),
) -> None:
    if os.path.lexists(os.path.join(paths.transaction_path, ROLLBACK_INVENTORY_FILENAME)) or (
        os.listdir(paths.rollback_old_path)
    ):
        raise StateError("Update rollback preparation already has evidence; recover it first.")
    replacement_roots = plan_replacement_roots(paths, edition, additional_roots)
    prepare_managed_data_commit(paths)
    persisted_state = write_rollback_inventory(
        paths, replacement_roots, state_files, state_directories
    )
    write_marker(paths.transaction_path, PREPARING_MARKER)
    copy_persisted_update_state(paths, persisted_state)
    copy_managed_data_to_rollback(paths)
    for item_name in replacement_roots:
        if not os.path.lexists(os.path.join(paths.base_path, item_name)):
            continue
        copy_install_entry(os.path.join(paths.base_path, item_name), paths.rollback_old_path)
        fsync_directory(paths.rollback_old_path, strict=True)
        fsync_directory(paths.base_path, strict=True)
    fsync_install_entry(paths.rollback_old_path)
    require_rollback_inventory(paths, old_complete=True)
    require_rollback_inventory(paths, old_complete=False, originals_at_installation=True)
    write_marker(paths.transaction_path, OLD_COMPLETE_MARKER)


def require_rollback_inventory(
    paths: UpdateTransactionPaths, *, old_complete: bool, originals_at_installation: bool = False
) -> UpdateRollbackInventory | None:
    inventory_path = os.path.join(paths.transaction_path, ROLLBACK_INVENTORY_FILENAME)
    if not os.path.lexists(inventory_path):
        if os.path.lexists(marker_path(paths.transaction_path, ROLLBACK_INVENTORY_REQUIRED_MARKER)):
            raise StateError(
                "Update rollback inventory is missing; preserve the transaction for repair."
            )
        return None
    payload = parse_json_dict(
        read_regular_file_no_symlink(inventory_path, max_bytes=1024 * 1024),
        field="update rollback inventory",
        reject_duplicate_keys=True,
    )
    roots = payload.get("replacement_roots")
    if (
        not is_str_list(roots)
        or any(name not in managed_root_entries("soai-os") for name in roots)
        or len(roots) != len(set(roots))
    ):
        raise StateError("Update replacement inventory is invalid.")
    entries = payload.get("paths")
    if (
        set(payload)
        != {
            "paths",
            "replacement_roots",
            "original_hashes",
            "persisted_destinations",
            "persisted_absent_parents",
            "persisted_directories",
            "runtime_directory",
        }
        or not is_str_list(entries)
        or len(entries) != len(set(entries))
    ):
        raise StateError(
            "Update rollback inventory is invalid; preserve the transaction for repair."
        )
    state = read_persisted_update_state(payload, paths, tuple(roots), entries)
    runtime_directory = payload.get("runtime_directory")
    if runtime_directory is not None and (
        not isinstance(runtime_directory, str)
        or runtime_directory not in state.directory_destinations
    ):
        raise StateError("Update runtime ownership does not match its directory inventory.")
    original_hashes = payload.get("original_hashes")
    if not isinstance(original_hashes, dict) or set(original_hashes) != set(entries):
        raise StateError("Update original fingerprints do not match the recorded inventory.")
    expected_roots = {entry.split("/", 1)[0] for entry in entries}
    if set(os.listdir(paths.rollback_old_path)).difference(expected_roots):
        raise StateError("Update rollback storage contains unrecorded content.")
    managed_entries = tuple(
        "/".join((MANAGED_ROLLBACK_DIR, *components))
        for components in (
            MANAGED_VENDOR_RELATIVE_COMPONENTS,
            MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
            MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
        )
    )
    for entry in entries:
        if entry not in roots and entry not in managed_entries and entry not in state.destinations:
            raise StateError("Update original inventory contains an unmanaged path.")
        source = safe_join_relative_under_base_lexical(
            base_path=paths.rollback_old_path,
            relative_path=entry,
            description="Update rollback original",
            error_cls=StateError,
        )
        if entry in managed_entries or entry in state.destinations:
            safe_join_relative_under_base(
                base_path=paths.rollback_old_path,
                relative_path=entry,
                description="Managed update rollback original",
                error_cls=StateError,
            )
            if os.path.islink(source):
                raise StateError("Managed update rollback original cannot be a symbolic link.")
        destination = _installed_original_path(paths, entry, state)
        if originals_at_installation:
            source = destination
        if not os.path.lexists(source):
            if old_complete or not os.path.lexists(destination):
                raise StateError(
                    "Update rollback original is missing; preserve the transaction for repair."
                )
            source = destination
        if entry in state.destinations:
            directory_original = destination in state.directory_destinations
            if (directory_original and not os.path.isdir(source)) or (
                not directory_original and not os.path.isfile(source)
            ):
                raise StateError(
                    "Update persisted original does not match its recorded entry type."
                )
        if _original_fingerprint(source) != original_hashes[entry]:
            raise StateError(
                "Update rollback original content is damaged; preserve the transaction for repair."
            )

    if originals_at_installation:
        if any(os.path.lexists(parent) for parent in state.absent_parents):
            raise StateError("Originally absent update state parents appeared during preparation.")
        for slot, destination in state.destinations.items():
            if slot not in state.original_entries and os.path.lexists(destination):
                raise StateError("Originally absent update state appeared during preparation.")
    return UpdateRollbackInventory(tuple(roots), state, runtime_directory)
