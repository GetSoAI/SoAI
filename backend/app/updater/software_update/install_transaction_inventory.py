"""SoAI - Durable update replacement inventory [backend/app/updater/software_update/install_transaction_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from app.backup.restore_destinations import ensure_restore_destination_is_safe
from app.updater.software_update.install_transaction_fingerprint import (
    FingerprintSnapshot,
    capture_fingerprint_snapshot,
)
from app.updater.software_update.install_transaction_persisted_state import (
    PersistedUpdateState,
    read_persisted_update_state,
)
from app.updater.software_update.install_transaction_state import (
    MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    MANAGED_ROLLBACK_DIR,
    MANAGED_VENDOR_RELATIVE_COMPONENTS,
    ROLLBACK_INVENTORY_REQUIRED_MARKER,
    UpdateTransactionPaths,
    marker_path,
)
from core.bootstrap.filename_layout import FILENAME_MAPPINGS
from core.bootstrap.install_payload import managed_root_entries, validate_existing_install_edition
from core.bootstrap.venv_paths import get_retained_venv_path, get_venv_path
from core.errors.exceptions import StateError
from core.files.path_policy import (
    is_path_overlap_with_base,
    safe_join_relative_under_base,
    safe_join_relative_under_base_lexical,
)
from core.filesystem.open_files import read_regular_file_no_symlink
from core.serialization.json_parsing import parse_json_dict
from core.types.json import is_str_list

__all__ = (
    "ROLLBACK_INVENTORY_FIELDS",
    "ROLLBACK_INVENTORY_FILENAME",
    "RollbackContentMismatch",
    "RollbackSourceFailure",
    "UpdateRollbackInventory",
    "inspect_rollback_inventory",
    "installed_original_path",
    "plan_replacement_roots",
    "require_rollback_inventory",
    "require_retained_installation_root",
)

ROLLBACK_INVENTORY_FILENAME = "rollback_inventory.json"
ROLLBACK_INVENTORY_FIELDS = frozenset(
    {
        "paths",
        "replacement_roots",
        "original_hashes",
        "persisted_destinations",
        "persisted_absent_parents",
        "persisted_directories",
        "runtime_directory",
    }
)


@dataclass(frozen=True, slots=True)
class UpdateRollbackInventory:
    replacement_roots: tuple[str, ...]
    persisted_state: PersistedUpdateState
    runtime_directory: str | None


@dataclass(frozen=True, slots=True)
class RollbackContentMismatch:
    entry: str
    entry_index: int
    source: str
    expected_aggregate: str
    actual: FingerprintSnapshot
    traversal_seconds: float


@dataclass(frozen=True, slots=True)
class RollbackSourceFailure:
    entry: str
    entry_index: int
    source: str
    exception: OSError | StateError


def require_retained_installation_root(
    base_path: str,
    retained_root: str,
    *,
    edition: str,
    expected_version: str | None = None,
) -> None:
    ensure_restore_destination_is_safe(retained_root)
    if not os.path.isdir(retained_root) or is_path_overlap_with_base(base_path, retained_root):
        raise StateError("Retained installer originals must be a separate regular directory.")
    validate_existing_install_edition(retained_root, edition)
    marker = read_regular_file_no_symlink(
        os.path.join(retained_root, ".soai-upgrade-backup"), max_bytes=128
    )
    if marker.rstrip(b"\r\n") != b"SoAI upgrade backup V1":
        raise StateError("Retained installer original authority is invalid.")
    if expected_version is not None:
        version = (
            read_regular_file_no_symlink(os.path.join(retained_root, "VERSION"), max_bytes=128)
            .decode("utf-8")
            .strip()
        )
        if version != expected_version:
            raise StateError("Retained installer original version conflicts with the transaction.")


def installed_original_path(
    paths: UpdateTransactionPaths,
    entry: str,
    state: PersistedUpdateState,
    *,
    retained_installation_root: str | None = None,
) -> str:
    if entry in state.destinations:
        destination = state.destinations[entry]
        if retained_installation_root is not None and destination == get_venv_path(paths.base_path):
            return get_retained_venv_path(paths.base_path, retained_installation_root)
        return destination
    return os.path.join(
        retained_installation_root or paths.base_path,
        *entry.removeprefix(f"{MANAGED_ROLLBACK_DIR}/").split("/"),
    )


def plan_replacement_roots(
    paths: UpdateTransactionPaths, edition: str, additional_roots: tuple[str, ...] = ()
) -> tuple[str, ...]:
    staged_roots = {name for name in os.listdir(paths.staged_new_path) if name != "data"}
    planned_roots = staged_roots.union(additional_roots)
    for original, canonical in FILENAME_MAPPINGS:
        if original in planned_roots or canonical in planned_roots:
            planned_roots.update(
                name
                for name in (original, canonical)
                if os.path.lexists(os.path.join(paths.base_path, name))
            )
    roots = tuple(sorted(planned_roots))
    owned_roots = managed_root_entries(edition)
    if any(name not in owned_roots for name in roots):
        raise StateError("Update payload contains content outside release ownership.")
    return roots


def inspect_rollback_inventory(
    paths: UpdateTransactionPaths,
    *,
    old_complete: bool,
    originals_at_installation: bool = False,
    verify_content: bool = True,
    retained_installation_root: str | None = None,
) -> UpdateRollbackInventory | RollbackContentMismatch | RollbackSourceFailure | None:
    inventory_path = os.path.join(paths.transaction_path, ROLLBACK_INVENTORY_FILENAME)
    if not os.path.lexists(inventory_path):
        if os.path.lexists(marker_path(paths.transaction_path, ROLLBACK_INVENTORY_REQUIRED_MARKER)):
            raise StateError(
                "Update rollback inventory is missing; preserve the transaction for repair."
            )
        return None
    if os.path.islink(paths.rollback_old_path) or not os.path.isdir(paths.rollback_old_path):
        raise StateError(
            "Update rollback storage is not a regular directory; preserve it for repair."
        )
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
        set(payload) != ROLLBACK_INVENTORY_FIELDS
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
    if (
        not isinstance(original_hashes, dict)
        or set(original_hashes) != set(entries)
        or not all(isinstance(value, str) for value in original_hashes.values())
    ):
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
    for entry_index, entry in enumerate(sorted(entries)):
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
        destination = installed_original_path(
            paths, entry, state, retained_installation_root=retained_installation_root
        )
        if originals_at_installation:
            source = destination
        if not os.path.lexists(source):
            if old_complete or not os.path.lexists(destination):
                raise StateError(
                    "Update rollback original is missing; preserve the transaction for repair."
                )
            source = destination
        if entry in state.destinations:
            directory_original = state.destinations[entry] in state.directory_destinations
            if (directory_original and not os.path.isdir(source)) or (
                not directory_original and not os.path.isfile(source)
            ):
                raise StateError(
                    "Update persisted original does not match its recorded entry type."
                )
        if verify_content:
            traversal_started = time.monotonic()
            try:
                actual = capture_fingerprint_snapshot(source)
            except (OSError, StateError) as exception:
                return RollbackSourceFailure(entry, entry_index, source, exception)
            if actual.aggregate != original_hashes[entry]:
                return RollbackContentMismatch(
                    entry,
                    entry_index,
                    source,
                    str(original_hashes[entry]),
                    actual,
                    time.monotonic() - traversal_started,
                )

    if originals_at_installation:
        if any(os.path.lexists(parent) for parent in state.absent_parents):
            raise StateError(
                "Originally absent update state parents appeared during preparation.",
                details={"classification": "absent_parent_appeared"},
            )
        for slot, destination in state.destinations.items():
            if slot not in state.original_entries and os.path.lexists(destination):
                raise StateError(
                    "Originally absent update state appeared during preparation.",
                    details={
                        "classification": "absent_destination_appeared",
                        "inventory_slot": slot,
                        "destination": destination,
                    },
                )
    return UpdateRollbackInventory(tuple(roots), state, runtime_directory)


def require_rollback_inventory(
    paths: UpdateTransactionPaths,
    *,
    old_complete: bool,
    originals_at_installation: bool = False,
    verify_content: bool = True,
    retained_installation_root: str | None = None,
) -> UpdateRollbackInventory | None:
    inspection = inspect_rollback_inventory(
        paths,
        old_complete=old_complete,
        originals_at_installation=originals_at_installation,
        verify_content=verify_content,
        retained_installation_root=retained_installation_root,
    )
    if isinstance(inspection, RollbackSourceFailure):
        raise inspection.exception
    if isinstance(inspection, RollbackContentMismatch):
        raise StateError(
            "Update rollback original content is damaged; preserve the transaction for repair.",
            details={
                "classification": "original_fingerprint_mismatch",
                "inventory_slot": inspection.entry,
                "source": inspection.source,
                "original_source": (
                    "retained" if retained_installation_root else "installation_or_snapshot"
                ),
            },
        )
    return inspection
