"""SoAI - Durable update rollback inventory writer [backend/app/updater/software_update/install_transaction_inventory_writer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from app.updater.disk_space import require_disk_space_for_update
from app.updater.software_update.activation_identity import UpdateActivationIdentity
from app.updater.software_update.install_transaction_fingerprint import capture_fingerprint_snapshot
from app.updater.software_update.install_transaction_inventory import (
    ROLLBACK_INVENTORY_FILENAME,
    installed_original_path,
)
from app.updater.software_update.install_transaction_persisted_state import (
    PersistedUpdateState,
    plan_persisted_update_state,
)
from app.updater.software_update.install_transaction_snapshot_evidence import (
    CHECK_INSTALLED_ORIGINAL,
    SnapshotProgress,
    build_operation_failure_report,
    record_snapshot_report,
    write_expected_descriptors,
)
from app.updater.software_update.install_transaction_state import (
    MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
    MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    MANAGED_ROLLBACK_DIR,
    MANAGED_VENDOR_RELATIVE_COMPONENTS,
    ROLLBACK_INVENTORY_REQUIRED_MARKER,
    UpdateTransactionPaths,
    write_marker,
)
from core.bootstrap.install_payload_transaction import install_entry_copy_size
from core.bootstrap.venv_paths import get_venv_path
from core.errors.exceptions import SoAIError
from core.filesystem.atomic_writes import atomic_write_json_content
from core.tasks.software_update_diagnostics import (
    UpdateDiagnosticsContext,
    establish_update_diagnostics,
)

__all__ = ("WrittenRollbackInventory", "write_rollback_inventory")


@dataclass(frozen=True, slots=True)
class WrittenRollbackInventory:
    state: PersistedUpdateState
    entries: tuple[str, ...]
    diagnostics: UpdateDiagnosticsContext


def write_rollback_inventory(
    paths: UpdateTransactionPaths,
    replacement_roots: tuple[str, ...],
    identity: UpdateActivationIdentity,
    state_files: tuple[str, ...] = (),
    state_directories: tuple[str, ...] = (),
    *,
    retained_installation_root: str | None = None,
) -> WrittenRollbackInventory:
    diagnostics = establish_update_diagnostics(
        base_path=paths.base_path,
        transaction_path=paths.transaction_path,
        task_id=identity.task_id,
        from_version=identity.from_version,
        to_version=identity.to_version,
        protected_trees=(*state_files, *state_directories),
    )
    state = plan_persisted_update_state(
        paths,
        replacement_roots,
        state_files,
        state_directories,
        retained_installation_root=retained_installation_root,
    )
    entries = [
        name
        for name in replacement_roots
        if os.path.lexists(os.path.join(retained_installation_root or paths.base_path, name))
    ]
    for components in (
        MANAGED_VENDOR_RELATIVE_COMPONENTS,
        MANAGED_CONFIG_DEFAULT_RELATIVE_COMPONENTS,
        MANAGED_INSTALL_METADATA_RELATIVE_COMPONENTS,
    ):
        if os.path.lexists(
            os.path.join(retained_installation_root or paths.base_path, *components)
        ):
            entries.append("/".join((MANAGED_ROLLBACK_DIR, *components)))
    entries.extend(state.original_entries)
    rollback_copy_bytes = sum(
        install_entry_copy_size(
            installed_original_path(
                paths, entry, state, retained_installation_root=retained_installation_root
            )
        )
        for entry in entries
    )
    require_disk_space_for_update(
        paths.base_path,
        rollback_copy_bytes + install_entry_copy_size(paths.staged_new_path),
        0,
        operation="application_updater.rollback_copy_space",
    )
    original_hashes: dict[str, str] = {}
    progress = SnapshotProgress(check=CHECK_INSTALLED_ORIGINAL)
    for index, entry in enumerate(sorted(entries)):
        try:
            progress.check = CHECK_INSTALLED_ORIGINAL
            snapshot = capture_fingerprint_snapshot(
                installed_original_path(
                    paths, entry, state, retained_installation_root=retained_installation_root
                )
            )
            progress.check = "snapshot_evidence"
            write_expected_descriptors(diagnostics, index=index, entry=entry, snapshot=snapshot)
        except (OSError, SoAIError) as exception:
            record_snapshot_report(
                diagnostics,
                build_operation_failure_report(
                    classification=(
                        "source_unverifiable"
                        if progress.check == CHECK_INSTALLED_ORIGINAL
                        else "snapshot_operation_failed"
                    ),
                    progress=progress,
                    entry=entry,
                    entry_index=index,
                    exception=exception,
                ),
                cause=exception,
            )
            raise
        original_hashes[entry] = snapshot.aggregate
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
    return WrittenRollbackInventory(state, tuple(sorted(entries)), diagnostics)
