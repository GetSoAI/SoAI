"""SoAI - Native Windows installer payload preparation [backend/app/updater/windows_installer_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from app.updater.disk_space import require_disk_space_for_update
from app.updater.release_bundle import PreparedReleaseBundle
from app.updater.software_update.update_payload_validation import (
    validate_and_prepare_staged_update,
)
from core.bootstrap.install_payload import managed_root_entries
from core.bootstrap.install_payload_transaction import copy_install_entry, install_entry_copy_size
from core.bootstrap.venv_paths import get_venv_path
from core.errors.exceptions import StateError
from core.files.path_policy import safe_join_relative_under_base
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.file_sync import fsync_install_entry
from core.filesystem.open_files import read_regular_file_no_symlink
from core.logging.protocols import LoggerProtocol
from core.runtime.process_identity_kill import (
    force_kill_process_tree_matching_identity_blocking,
)
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.serialization.json_parsing import parse_json_dict
from core.system.process_launcher import DEVNULL_STREAM, spawn_handoff_process
from core.system.subprocess_platform import windows_isolated_process_creationflags
from core.timing.constants import CONTROL_TIMEOUT_SEC, SETUP_TIMEOUT_SEC
from core.types.json import is_str_list

if TYPE_CHECKING:
    from app.updater.software_update.install_transaction_state import UpdateTransactionPaths
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "PreparedWindowsInstaller",
    "prepare_windows_installer_payload",
    "retain_windows_recovery_runtime",
)

RECOVERY_RUNTIME_DIRECTORY = "recovery_runtime"


@dataclass(frozen=True, slots=True)
class PreparedWindowsInstaller:
    staged_root: str
    state_files: tuple[str, ...]
    state_directories: tuple[str, ...]


def _read_native_rollback_inventory(staged_root: str, base_path: str) -> PreparedWindowsInstaller:
    payload = parse_json_dict(
        read_regular_file_no_symlink(f"{staged_root}.inventory.json", max_bytes=1024 * 1024),
        field="Windows installer rollback inventory",
        reject_duplicate_keys=True,
    )
    files = payload.get("files")
    directories = payload.get("directories")
    if (
        set(payload) != {"files", "directories"}
        or not is_str_list(files)
        or not is_str_list(directories)
    ):
        raise StateError("Windows installer rollback inventory fields are invalid.")
    if not files or not directories:
        raise StateError("Windows installer rollback inventory is incomplete.")
    resolved_files = tuple(
        safe_join_relative_under_base(
            base_path=base_path,
            relative_path=relative,
            description="Windows installer rollback file",
            error_cls=StateError,
        )
        for relative in files
    )
    resolved_directories = tuple(
        safe_join_relative_under_base(
            base_path=base_path,
            relative_path=relative,
            description="Windows installer rollback directory",
            error_cls=StateError,
        )
        for relative in directories
    )
    all_paths = (*resolved_files, *resolved_directories)
    if len({os.path.normcase(path) for path in all_paths}) != len(all_paths):
        raise StateError("Windows installer rollback inventory has conflicting paths.")
    for path in resolved_files:
        if os.path.lexists(path) and not os.path.isfile(path):
            raise StateError("Windows installer rollback file is not a regular file.")
    for path in resolved_directories:
        if os.path.lexists(path) and not os.path.isdir(path):
            raise StateError("Windows installer rollback directory is not a directory.")
    require_disk_space_for_update(
        base_path,
        sum(install_entry_copy_size(path) for path in all_paths if os.path.lexists(path)),
        0,
        operation="application_updater.windows_rollback_space",
    )
    return PreparedWindowsInstaller(staged_root, resolved_files, resolved_directories)


@contextmanager
def prepare_windows_installer_payload(
    *,
    command: list[str],
    temp_path: str,
    base_path: str,
    release_bundle: PreparedReleaseBundle,
    logger: LoggerProtocol,
) -> Generator[PreparedWindowsInstaller]:
    preparation_root = tempfile.mkdtemp(prefix="soai-update-prepare-", dir=temp_path)
    staged_root = os.path.join(preparation_root, "payload")
    process_handle = None
    process_create_time_ms = None
    cleanup_safe = True
    try:
        try:
            os.mkdir(staged_root)
            process_handle = spawn_handoff_process(
                [*command, "-StageRoot", staged_root],
                cwd=preparation_root,
                creationflags=windows_isolated_process_creationflags(),
                stdin=DEVNULL_STREAM,
                stdout=DEVNULL_STREAM,
                stderr=DEVNULL_STREAM,
            )
            cleanup_safe = False
            process_create_time_ms = read_process_create_time_ms(psutil.Process(process_handle.pid))
            exit_code = process_handle.wait(timeout=SETUP_TIMEOUT_SEC + 2 * CONTROL_TIMEOUT_SEC)
            exit_witness = read_regular_file_no_symlink(f"{staged_root}.exited", max_bytes=128)
            cleanup_safe = exit_witness.strip() == str(process_handle.pid).encode("ascii")
            if not cleanup_safe:
                raise StateError("Windows installer preparation did not verify process exit.")
            if exit_code != 0:
                raise StateError(
                    "Windows installer preparation failed before application shutdown.",
                    details={"exit_code": exit_code},
                )
            validate_and_prepare_staged_update(
                staged_root=staged_root,
                platform_id="windows-x64",
                artifact_record=release_bundle.artifact_record,
                manifest=release_bundle.manifest,
                updater=release_bundle.updater,
            )
        except psutil.Error as exception:
            raise StateError(
                "Windows installer preparation process identity is unavailable."
            ) from exception
        yield _read_native_rollback_inventory(staged_root, base_path)
    finally:
        if (
            process_handle is not None
            and not cleanup_safe
            and process_handle.poll() is None
            and process_create_time_ms is not None
        ):
            termination = force_kill_process_tree_matching_identity_blocking(
                process_handle.pid,
                process_create_time_ms,
                "Windows installer preparation",
                logger,
            )
            if termination.success and not termination.process_not_found:
                process_handle.wait(timeout=CONTROL_TIMEOUT_SEC)
                cleanup_safe = True
        if not cleanup_safe:
            logger.error(
                "Windows preparation cleanup needs repair; retained evidence at %s.",
                preparation_root,
            )
            raise StateError("Windows installer preparation could not establish safe cleanup.")
        shutil.rmtree(preparation_root)


def retain_windows_recovery_runtime(
    paths: UpdateTransactionPaths, reservation_provider: StorageManagerProtocol
) -> str:
    source = safe_join_relative_under_base(
        base_path=paths.base_path,
        relative_path=os.path.relpath(sys.base_prefix, paths.base_path),
        description="Windows standalone recovery interpreter",
        error_cls=StateError,
    )
    if os.path.normcase(source) in {
        os.path.normcase(paths.base_path),
        os.path.normcase(get_venv_path(paths.base_path)),
    }:
        raise StateError("Windows recovery requires the standalone Python installation.")
    executable = safe_join_relative_under_base(
        base_path=source,
        relative_path="python.exe",
        description="Windows recovery interpreter executable",
        error_cls=StateError,
    )
    if not os.path.isfile(executable):
        raise StateError("The Windows standalone recovery interpreter is missing.")
    retained = os.path.join(paths.transaction_path, RECOVERY_RUNTIME_DIRECTORY)
    job_root = os.path.join(paths.transaction_path, "native_job")
    job_files = tuple(
        safe_join_relative_under_base(
            base_path=paths.base_path,
            relative_path=name,
            description="Windows native recovery dependency",
            error_cls=StateError,
        )
        for name in managed_root_entries("soai-core")
        if name == "soai.exe" or name.endswith(".dll")
    )
    if not os.path.isfile(os.path.join(paths.base_path, "soai.exe")):
        raise StateError("The Windows recovery process owner is missing.")
    job_files = tuple(path for path in job_files if os.path.lexists(path))
    if any(not os.path.isfile(path) for path in job_files):
        raise StateError("Windows recovery dependencies must be regular files.")
    if os.path.lexists(retained) or os.path.lexists(job_root):
        raise StateError("Windows recovery runtime retention already has evidence.")
    required_bytes = install_entry_copy_size(source) + sum(
        install_entry_copy_size(path) for path in job_files
    )
    with reservation_provider.reserve_disk_space(
        path=retained,
        required_bytes=required_bytes,
        operation="application_updater.windows_recovery_runtime",
        details={},
    ) as reservation:
        with reservation.claim_write_bytes(required_bytes) as claim:
            for name in os.listdir(source):
                copy_install_entry(os.path.join(source, name), retained)
            for path in job_files:
                copy_install_entry(path, job_root)
            os.rename(
                os.path.join(job_root, "soai.exe"), os.path.join(job_root, "soai-job-owner.dll")
            )
            fsync_install_entry(job_root)
            fsync_install_entry(retained)
            fsync_directory(paths.transaction_path, strict=True)
            claim.commit()
    return os.path.join(retained, "python.exe")
