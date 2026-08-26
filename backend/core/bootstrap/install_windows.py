"""SoAI - Windows install command implementation [backend/core/bootstrap/install_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import subprocess
import time
from typing import TYPE_CHECKING

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.bootstrap.install_arguments import ParsedInstallArguments
from core.bootstrap.install_filesystem import unlink_if_exists
from core.bootstrap.install_locks import (
    INSTALL_LOCK_ENV,
    acquire_lock_dir,
    release_lock_dir,
    wait_for_lock_dir_clear,
)
from core.bootstrap.install_payload import validate_existing_install_edition
from core.bootstrap.install_payload_transaction import copy_managed_payload
from core.bootstrap.install_status import InstallStatusOptions, InstallStatusReporter
from core.bootstrap.install_target_windows import (
    normalize_windows_install_target,
    recognizable_windows_install_target,
    reject_running_windows_target,
    validate_windows_install_target,
)
from core.errors.exceptions import SoAIError, SoAITimeoutError, ValidationError
from core.meta.paths import join_data_abs
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
        with open(version_path, encoding="utf-8", errors="strict") as version_file:
            version = version_file.read().strip()
    except (OSError, UnicodeDecodeError) as exception:
        raise ValidationError("SoAI Core VERSION is missing or unreadable.") from exception
    if not version or any(character.isspace() for character in version):
        raise ValidationError("SoAI Core VERSION is invalid.")
    return version


def wait_for_windows_install_to_finish(repo_root_path: str) -> None:
    marker_path = os.path.join(repo_root_path, ".soai_install_in_progress")
    lock_dir = join_data_abs(repo_root_path, "state", "locks", "soai.install.lock.d")
    started = time.monotonic()
    while os.path.isfile(marker_path) or os.path.isdir(lock_dir):
        if os.path.isdir(lock_dir):
            wait_for_lock_dir_clear(lock_dir)
            continue
        if time.monotonic() - started >= 1200.0:
            raise SoAITimeoutError(
                "Timed out waiting for SoAI install marker to clear.",
                details={"marker_path": marker_path},
                operation="bootstrap.install.wait_for_install_to_finish",
            )
        sleep_seconds(1.0)


def install_to_target(
    source_root: str,
    parsed_args: ParsedInstallArguments,
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
    validate_windows_install_target(target_root)
    if not recognizable_windows_install_target(target_root):
        raise ValidationError(
            "Install target exists but is not an empty or recognizable SoAI directory.",
            details={"target_root": target_root},
            operation="bootstrap.install.validate_target",
        )
    lock_dir = acquire_lock_dir(join_data_abs(target_root, "state", "locks", "soai.install.lock.d"))
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
        release_lock_dir(lock_dir)


def run_target_install_deps(
    target_root: str,
    parsed_args: ParsedInstallArguments,
    lock_dir: str,
) -> None:
    launcher_path = os.path.join(target_root, "soai.exe")
    if not os.path.isfile(launcher_path):
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
        with open(marker_path, "w", encoding="utf-8", errors="strict") as handle:
            handle.write(marker_text)
        claim.commit()


def _remove_in_progress_marker(target_root: str) -> None:
    unlink_if_exists(os.path.join(target_root, ".soai_install_in_progress"))
