"""SoAI - Verified Windows setup update execution [backend/app/updater/windows_installer_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.updater.download import download_update_file
from app.updater.release_bundle import PreparedReleaseBundle
from app.updater.release_manifest_types import ReleaseInstaller
from app.updater.software_update.activation_state import record_update_activation_identity
from app.updater.software_update.install_transaction_recovery import (
    recover_interrupted_update_transactions,
)
from app.updater.software_update.install_transaction_state import allocate_update_transaction
from app.updater.software_update.update_lock import (
    resolve_software_update_lock_dir,
    transfer_software_update_lock,
)
from app.updater.windows_installer_preparation import (
    prepare_windows_installer_payload,
    retain_windows_recovery_runtime,
)
from app.updater.windows_update_transaction import prepare_windows_update_transaction
from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError, StateError, ValidationError
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol
from core.process.termination import terminate_process_and_wait
from core.system.process_launcher import (
    DEVNULL_STREAM,
    SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    spawn_handoff_process,
)
from core.system.subprocess_platform import windows_isolated_process_creationflags
from core.timing.constants import (
    BACKGROUND_TIMEOUT_SEC,
    CONTROL_TIMEOUT_SEC,
    SHORT_POLL_INTERVAL_SEC,
)
from core.timing.sleep import sleep_seconds

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("perform_windows_installer_update",)

OPERATION = "application_updater.windows_installer_update"
OPERATION_CLEANUP = "application_updater.windows_installer_update.cleanup"
HANDOFF_SCRIPT_NAME = "windows_installer_handoff.ps1"
HANDOFF_EXCEPTIONS: tuple[type[Exception], ...] = (
    *SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    InsufficientDiskSpaceError,
    StateError,
    ValidationError,
)


def _copy_handoff_script(temp_path: str) -> str:
    source_path = os.path.join(os.path.dirname(__file__), HANDOFF_SCRIPT_NAME)
    file_descriptor, handoff_path = tempfile.mkstemp(suffix=".ps1", dir=temp_path)
    os.close(file_descriptor)
    try:
        shutil.copyfile(source_path, handoff_path)
    except OSError:
        os.remove(handoff_path)
        raise
    return handoff_path


def _handoff_is_ready(
    process_handle: subprocess.Popen[str] | subprocess.Popen[bytes],
    ready_path: str,
) -> bool:
    deadline = deadline_after(BACKGROUND_TIMEOUT_SEC)
    while not deadline.expired():
        if process_handle.poll() is not None:
            return False
        try:
            with open_text(ready_path, encoding="ascii", errors="replace") as file_handle:
                ready_process_id = file_handle.read().strip()
        except FileNotFoundError:
            ready_process_id = None
        if ready_process_id == str(process_handle.pid):
            return True
        sleep_seconds(SHORT_POLL_INTERVAL_SEC)
    return False


def perform_windows_installer_update(
    *,
    logger: LoggerProtocol,
    base_path: str,
    temp_path: str,
    config: ConfigProtocol,
    config_path: str,
    download_timeout: float,
    release_bundle: PreparedReleaseBundle,
    reservation_provider: StorageManagerProtocol,
    restart_after_update: Callable[[], bool],
    before_handoff: Callable[[], bool],
    task_id: str,
    from_version: str,
) -> bool:
    installer_record = release_bundle.artifact_record
    if not isinstance(installer_record, ReleaseInstaller):
        raise ValidationError("Windows installer update received a non-installer artifact.")
    downloaded_installer = None
    handoff_path = None
    ready_path = None
    handoff_started = False
    transaction_paths = None
    try:
        logger.info("Downloading manifest-authenticated Windows update installer...")
        downloaded_installer = download_update_file(
            logger,
            url=release_bundle.artifact_download_url,
            timeout=download_timeout,
            temp_path=temp_path,
            max_download_bytes=installer_record.size_bytes,
            reservation_provider=reservation_provider,
            suffix=".exe",
        )
        if downloaded_installer is None:
            return False
        if (
            downloaded_installer.size_bytes != installer_record.size_bytes
            or downloaded_installer.sha256_hex != release_bundle.expected_artifact_sha256
        ):
            logger.error("Downloaded Windows installer does not match its signed release record.")
            return False
        windows_directory = os.environ.get("WINDIR", "").strip()
        if not windows_directory:
            raise ValidationError("Windows installer handoff requires WINDIR.")
        powershell_path = os.path.join(
            windows_directory,
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe",
        )
        if not os.path.isfile(powershell_path):
            raise ValidationError("Windows PowerShell is unavailable for installer handoff.")
        handoff_path = _copy_handoff_script(temp_path)
        ready_path = f"{handoff_path}.ready"
        lock_dir = resolve_software_update_lock_dir(base_path)
        command = [
            powershell_path,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-NonInteractive",
            "-File",
            handoff_path,
            "-SetupPath",
            downloaded_installer.file_path,
            "-InstallRoot",
            base_path,
            "-LockDir",
            lock_dir,
            "-ReadyPath",
            ready_path,
            "-TaskId",
            task_id,
            "-ToVersion",
            release_bundle.manifest.version,
            "-UpdaterPid",
            str(os.getpid()),
        ]
        transaction_paths = allocate_update_transaction(base_path)
        record_update_activation_identity(
            transaction_paths,
            task_id=task_id,
            edition=release_bundle.updater.edition,
            from_version=from_version,
            to_version=release_bundle.manifest.version,
            config_path=config_path,
        )
        retain_windows_recovery_runtime(transaction_paths, reservation_provider)
        command.extend(("-TransactionPath", transaction_paths.transaction_path))
        with prepare_windows_installer_payload(
            command=command,
            temp_path=temp_path,
            base_path=base_path,
            release_bundle=release_bundle,
            logger=logger,
        ) as prepared_installer:
            if not prepare_windows_update_transaction(
                paths=transaction_paths,
                prepared=prepared_installer,
                release_bundle=release_bundle,
                config=config,
                config_path=config_path,
                task_id=task_id,
                from_version=from_version,
                reservation_provider=reservation_provider,
                before_handoff=before_handoff,
            ):
                return False
        if restart_after_update():
            command.append("-RestartAfterUpdate")
        logger.info("Handing the verified Windows update to the installer...")
        environment = dict(os.environ)
        environment["SOAI_CONFIG_PATH"] = config_path
        process_handle = spawn_handoff_process(
            command,
            cwd=temp_path,
            env=environment,
            creationflags=windows_isolated_process_creationflags(),
            stdin=DEVNULL_STREAM,
            stdout=DEVNULL_STREAM,
            stderr=DEVNULL_STREAM,
        )
        if not _handoff_is_ready(process_handle, ready_path):
            terminate_process_and_wait(process_handle, timeout_sec=CONTROL_TIMEOUT_SEC)
            raise ValidationError("Windows installer handoff failed to become ready.")
        try:
            transfer_software_update_lock(lock_dir, process_handle.pid)
        except (OSError, StateError):
            terminate_process_and_wait(process_handle, timeout_sec=CONTROL_TIMEOUT_SEC)
            raise
        handoff_started = True
        return True
    except HANDOFF_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Windows installer update failed.",
            operation=OPERATION,
            level="error",
        )
        return False
    finally:
        if (
            not handoff_started
            and downloaded_installer is not None
            and os.path.exists(downloaded_installer.file_path)
        ):
            try:
                os.remove(downloaded_installer.file_path)
            except OSError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to remove downloaded Windows installer.",
                    operation=OPERATION_CLEANUP,
                    details={"path": downloaded_installer.file_path},
                    level="warning",
                )
        if not handoff_started and ready_path is not None and os.path.exists(ready_path):
            try:
                os.remove(ready_path)
            except OSError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to remove Windows installer handoff readiness file.",
                    operation=OPERATION_CLEANUP,
                    details={"path": ready_path},
                    level="warning",
                )
        if not handoff_started and handoff_path is not None and os.path.exists(handoff_path):
            try:
                os.remove(handoff_path)
            except OSError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to remove Windows installer handoff script.",
                    operation=OPERATION_CLEANUP,
                    details={"path": handoff_path},
                    level="warning",
                )
        if not handoff_started and transaction_paths is not None:
            if not recover_interrupted_update_transactions(base_path, logger):
                raise StateError("Windows update preparation recovery requires repair.")
