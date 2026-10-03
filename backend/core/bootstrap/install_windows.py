"""SoAI - Windows install command implementation [backend/core/bootstrap/install_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from contextlib import ExitStack
from typing import TYPE_CHECKING

import psutil

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.install_arguments import ParsedInstallArguments
from core.bootstrap.install_filesystem import unlink_if_exists
from core.bootstrap.install_lock_recovery import (
    recover_windows_install_lock,
    recover_windows_startup_install_lock,
)
from core.bootstrap.install_locks import (
    INSTALL_LOCK_ENV,
    INSTALL_LOCK_OWNER_START_ENV,
    INSTALL_LOCK_TOKEN_ENV,
    LOCK_TIMEOUT_SECONDS,
    acquire_lock_dir,
    guard_windows_installer_gate,
    read_lock_token,
    release_lock_dir,
)
from core.bootstrap.install_payload import validate_existing_install_edition
from core.bootstrap.install_payload_transaction import copy_managed_payload
from core.bootstrap.install_status import InstallStatusOptions, InstallStatusReporter
from core.bootstrap.install_target_windows import (
    create_windows_install_directories,
    normalize_windows_install_target,
    recognizable_windows_install_target,
    reject_running_windows_target,
    retain_windows_install_ancestors,
    validate_windows_install_target,
    validate_windows_launcher_configuration,
)
from core.bootstrap.lock import INSTALLATION_TRANSACTION_LOCK_FILENAME, acquire_interprocess_lock
from core.errors.exceptions import ConflictError, SoAIError, SoAITimeoutError, ValidationError
from core.filesystem.path_coercion import normalize_filesystem_path
from core.meta.paths import join_data_abs
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.system.process_launcher import spawn_managed_process
from core.timing.sleep import sleep_seconds

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "default_windows_install_target",
    "install_to_target",
    "run_target_install_deps",
    "wait_for_windows_install_to_finish",
)


def default_windows_install_target() -> str:
    program_files = os.environ.get("ProgramFiles", "").strip()
    if not program_files:
        system_drive = os.environ.get("SystemDrive", "C:").strip() or "C:"
        program_files = os.path.join(system_drive, "Program Files")
    return os.path.abspath(os.path.join(program_files, "SoAI"))


def _read_source_version(source_root: str) -> str:
    version_path = os.path.join(source_root, "VERSION")
    try:
        with open(
            normalize_filesystem_path(version_path), encoding="utf-8", errors="strict"
        ) as version_file:
            version = version_file.read().strip()
    except (OSError, UnicodeDecodeError) as exception:
        raise ValidationError("SoAI Core VERSION is missing or unreadable.") from exception
    if not version or any(character.isspace() for character in version):
        raise ValidationError("SoAI Core VERSION is invalid.")
    return version


def wait_for_windows_install_to_finish(
    repo_root_path: str,
    check_transaction_admission: Callable[[str], None],
) -> None:
    marker_path = os.path.join(repo_root_path, ".soai_install_in_progress")
    lock_dir = join_data_abs(repo_root_path, "state", "locks", "soai.install.lock.d")
    started = time.monotonic()
    while os.path.isfile(marker_path) or os.path.isdir(lock_dir):
        if time.monotonic() - started >= LOCK_TIMEOUT_SECONDS:
            raise SoAITimeoutError(
                "Timed out waiting for SoAI installation ownership to clear.",
                details={"marker_path": marker_path, "lock_dir": lock_dir},
                operation="bootstrap.install.wait_for_install_to_finish",
            )
        try:
            available = recover_windows_startup_install_lock(
                repo_root_path, check_transaction_admission
            )
        except ConflictError:
            sleep_seconds(1.0)
            continue
        if not available:
            sleep_seconds(1.0)


def install_to_target(
    source_root: str,
    parsed_args: ParsedInstallArguments,
    check_transaction_admission: Callable[[str], None],
) -> None:
    source_version = _read_source_version(source_root)
    target_root = normalize_windows_install_target(parsed_args.target)
    reporter = InstallStatusReporter(
        InstallStatusOptions(
            silent=parsed_args.silent,
            json_events=parsed_args.json_events,
            status_file=parsed_args.status_file,
        ),
    )
    validate_windows_install_target(target_root, create=False)
    if not recognizable_windows_install_target(target_root):
        raise ValidationError(
            "Install target exists but is not an empty or recognizable SoAI directory.",
            details={"target_root": target_root},
            operation="bootstrap.install.validate_target",
        )
    mutation_scope = ExitStack()
    admitted = False
    try:
        mutation_scope.enter_context(guard_windows_installer_gate())
        retain_windows_install_ancestors(target_root, mutation_scope)
        validate_windows_install_target(target_root, create=False)
        if not recognizable_windows_install_target(target_root):
            raise ValidationError("Install target changed before exclusive admission.")
        create_windows_install_directories(target_root, mutation_scope)
        validate_windows_install_target(target_root)
        create_windows_install_directories(join_data_abs(target_root, "locks"), mutation_scope)
        create_windows_install_directories(
            join_data_abs(target_root, "state", "locks"), mutation_scope
        )
        mutation_scope.enter_context(
            acquire_interprocess_lock(
                join_data_abs(target_root, "locks", INSTALLATION_TRANSACTION_LOCK_FILENAME),
                timeout_sec=30.0,
            )
        )
        check_transaction_admission(target_root)
        validate_windows_launcher_configuration(source_root, target_root)
        recover_windows_install_lock(
            join_data_abs(target_root, "state", "locks", "soai.install.lock.d"),
            os.path.join(source_root, "soai.exe"),
        )
        lock = acquire_lock_dir(join_data_abs(target_root, "state", "locks", "soai.install.lock.d"))
        admitted = True
    finally:
        if not admitted:
            mutation_scope.close()
    lock_dir = lock.path
    copy_succeeded = False
    try:
        reject_running_windows_target(target_root, expected_edition="soai-core")
        validate_existing_install_edition(target_root, "soai-core")
        reservation_provider = create_bootstrap_disk_reservation_provider(target_root)
        _write_in_progress_marker(target_root, reservation_provider=reservation_provider)
        reporter.emit_stage(
            install_root=target_root,
            operation="install",
            stage="copy",
            state="started",
            message=f"Installing SoAI application files to {target_root}...",
        )
        try:
            copy_managed_payload(
                source_root,
                target_root,
                reservation_provider=reservation_provider,
                edition="soai-core",
                product_version=source_version,
                core_version=source_version,
            )
            copy_succeeded = True
        except (OSError, SoAIError, ValueError):
            reporter.emit_stage(
                install_root=target_root,
                operation="install",
                stage="copy",
                state="failed",
                message=f"SoAI application file install failed for {target_root}.",
            )
            _remove_in_progress_marker(target_root)
            raise
        reporter.emit_stage(
            install_root=target_root,
            operation="install",
            stage="copy",
            state="completed",
            message=f"SoAI application files are installed at {target_root}.",
        )
        reporter.emit_stage(
            install_root=target_root,
            operation="install",
            stage="dependencies",
            state="started",
            message=f"Provisioning SoAI runtime dependencies in {target_root}...",
        )
        try:
            run_target_install_deps(target_root, parsed_args, lock_dir)
        except (OSError, SoAIError, ValueError, subprocess.SubprocessError):
            reporter.emit_stage(
                install_root=target_root,
                operation="install",
                stage="dependencies",
                state="failed",
                message=f"SoAI runtime dependency provisioning failed in {target_root}.",
            )
            _remove_in_progress_marker(target_root)
            raise
        reporter.emit_stage(
            install_root=target_root,
            operation="install",
            stage="dependencies",
            state="completed",
            message=f"SoAI runtime dependencies are ready in {target_root}.",
        )
        reporter.emit_stage(
            install_root=target_root,
            operation="install",
            stage="complete",
            state="completed",
            message=f"SoAI install completed successfully at {target_root}.",
        )
    finally:
        if not copy_succeeded:
            _remove_in_progress_marker(target_root)
        try:
            release_lock_dir(lock)
        finally:
            mutation_scope.close()


def run_target_install_deps(
    target_root: str,
    parsed_args: ParsedInstallArguments,
    lock_dir: str,
) -> None:
    launcher_path = os.path.join(target_root, "soai.exe")
    if not os.path.isfile(normalize_filesystem_path(launcher_path)):
        raise FileNotFoundError(f"Windows install requires target launcher: {launcher_path}")
    command = [launcher_path, "install-deps"]
    if parsed_args.json_events:
        command.append("--json-events")
    if parsed_args.status_file:
        command.extend(["--status-file", parsed_args.status_file])
    if parsed_args.silent:
        command.append("--silent")
    command.extend(parsed_args.passthrough_args)
    env = dict(os.environ)
    env[INSTALL_LOCK_ENV] = lock_dir
    lock_token = read_lock_token(lock_dir)
    if lock_token is None:
        raise ValidationError("SoAI install lock handoff token is missing or invalid.")
    env[INSTALL_LOCK_TOKEN_ENV] = lock_token
    env[INSTALL_LOCK_OWNER_START_ENV] = str(read_process_create_time_ms(psutil.Process()))
    with spawn_managed_process(command, cwd=target_root, env=env) as process:
        exit_code = process.wait()
    if exit_code != 0:
        raise subprocess.CalledProcessError(exit_code, command)


def _write_in_progress_marker(
    target_root: str,
    *,
    reservation_provider: StorageManagerProtocol,
) -> None:
    marker_path = os.path.join(target_root, ".soai_install_in_progress")
    marker_text = "installing\n"
    marker_bytes = marker_text.encode("utf-8")
    with (
        reservation_provider.reserve_disk_space(
            path=marker_path,
            required_bytes=len(marker_bytes),
            operation="core.bootstrap.install_windows.write_in_progress_marker",
            details={"marker_path": marker_path},
        ) as reservation,
        reservation.claim_write_bytes(len(marker_bytes)) as claim,
    ):
        with open(
            normalize_filesystem_path(marker_path), "w", encoding="utf-8", errors="strict"
        ) as handle:
            handle.write(marker_text)
        claim.commit()


def _remove_in_progress_marker(target_root: str) -> None:
    unlink_if_exists(os.path.join(target_root, ".soai_install_in_progress"))
