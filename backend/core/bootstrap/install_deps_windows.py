"""SoAI - Windows install-deps progress session [backend/core/bootstrap/install_deps_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass

from core.bootstrap.install_arguments import ParsedInstallArguments
from core.bootstrap.install_lock_recovery import recover_windows_install_lock
from core.bootstrap.install_locks import (
    INSTALL_LOCK_ENV,
    INSTALL_LOCK_OWNER_START_ENV,
    INSTALL_LOCK_TOKEN_ENV,
    InstallDirectoryLock,
    acquire_lock_dir,
    guard_windows_installer_gate,
    inherited_install_lock_is_valid,
    publish_install_lock_environment,
    release_lock_dir,
)
from core.bootstrap.install_status import InstallStatusOptions, InstallStatusReporter
from core.bootstrap.install_target_windows import (
    create_windows_install_directories,
    reject_running_windows_target,
    retain_windows_install_ancestors,
    validate_windows_install_target,
)
from core.bootstrap.lock import INSTALLATION_TRANSACTION_LOCK_FILENAME, acquire_interprocess_lock
from core.errors.exceptions import ProcessError, StateError
from core.meta.paths import join_data_abs
from core.system.commands import run_argv_capture

__all__ = ("WindowsInstallDepsSession", "begin_windows_install_deps")


@dataclass(slots=True)
class WindowsInstallDepsSession:
    repo_root_path: str
    reporter: InstallStatusReporter
    lock_dir: str
    owned_lock: InstallDirectoryLock | None
    mutation_scope: ExitStack
    post_update_hook_module: str = "app.updater.post_update_hook"

    def complete(self, python_executable: str) -> None:
        self.emit("managed-runtime", "completed", "SoAI managed runtime is ready.")
        self.emit("runtime-artifacts", "started", "Provisioning SoAI runtime artifacts...")
        self.emit("runtime-artifacts", "completed", "SoAI runtime artifacts are ready.")
        self.emit("migration-hook", "started", "Running SoAI V1 post-install migration hook...")
        _run_post_update_hook(
            self.repo_root_path, python_executable, hook_module=self.post_update_hook_module
        )
        self.emit("migration-hook", "completed", "SoAI V1 post-install migration hook completed.")
        self.emit("complete", "completed", "SoAI dependency installation completed successfully.")
        self.release()

    def fail(self, stage: str, message: str) -> None:
        try:
            self.emit(stage, "failed", message)
        finally:
            self.release()

    def emit(self, stage: str, state: str, message: str) -> None:
        self.reporter.emit_stage(
            install_root=self.repo_root_path,
            operation="install-deps",
            stage=stage,
            state=state,
            message=message,
        )

    def release(self) -> None:
        lock = self.owned_lock
        if lock is None:
            self.mutation_scope.close()
            return
        self.owned_lock = None
        try:
            release_lock_dir(lock)
            if os.environ.get(INSTALL_LOCK_TOKEN_ENV, "") == lock.token:
                os.environ.pop(INSTALL_LOCK_ENV, None)
                os.environ.pop(INSTALL_LOCK_TOKEN_ENV, None)
                os.environ.pop(INSTALL_LOCK_OWNER_START_ENV, None)
        finally:
            self.mutation_scope.close()


def begin_windows_install_deps(
    repo_root_path: str,
    parsed_args: ParsedInstallArguments,
    check_transaction_admission: Callable[[str], None],
    *,
    expected_edition: str = "soai-core",
    post_update_hook_module: str = "app.updater.post_update_hook",
) -> WindowsInstallDepsSession:
    lock_dir = join_data_abs(repo_root_path, "state", "locks", "soai.install.lock.d")
    mutation_scope = ExitStack()
    owned_lock: InstallDirectoryLock | None = None
    admitted = False
    try:
        inherited = inherited_install_lock_is_valid(lock_dir)
        mutation_scope.enter_context(guard_windows_installer_gate(inherited=inherited))
        retain_windows_install_ancestors(repo_root_path, mutation_scope)
        if not inherited:
            validate_windows_install_target(repo_root_path, create=False)
            create_windows_install_directories(
                join_data_abs(repo_root_path, "locks"), mutation_scope
            )
            create_windows_install_directories(
                join_data_abs(repo_root_path, "state", "locks"), mutation_scope
            )
            mutation_scope.enter_context(
                acquire_interprocess_lock(
                    join_data_abs(repo_root_path, "locks", INSTALLATION_TRANSACTION_LOCK_FILENAME),
                    timeout_sec=30.0,
                )
            )
            check_transaction_admission(repo_root_path)
            recover_windows_install_lock(lock_dir, os.path.join(repo_root_path, "soai.exe"))
            owned_lock = acquire_lock_dir(lock_dir)
            publish_install_lock_environment(owned_lock)
        admitted = True
    finally:
        if not admitted:
            try:
                if owned_lock is not None:
                    release_lock_dir(owned_lock)
            finally:
                mutation_scope.close()
    reporter = InstallStatusReporter(
        InstallStatusOptions(
            silent=parsed_args.silent,
            json_events=parsed_args.json_events,
            status_file=parsed_args.status_file,
        ),
    )
    session = WindowsInstallDepsSession(
        repo_root_path=repo_root_path,
        reporter=reporter,
        lock_dir=lock_dir,
        owned_lock=owned_lock,
        mutation_scope=mutation_scope,
        post_update_hook_module=post_update_hook_module,
    )
    try:
        session.emit("preflight", "started", "Checking SoAI runtime state...")
        reject_running_windows_target(repo_root_path, expected_edition=expected_edition)
        session.emit("preflight", "completed", "SoAI is not running.")
        session.emit("managed-runtime", "started", "Preparing SoAI managed runtime...")
    except StateError:
        message = "Refusing to install dependencies while SoAI is starting or running."
        try:
            session.fail("preflight", message)
        except OSError:
            session.release()
        raise
    except (OSError, ValueError):
        session.release()
        raise
    return session


def _run_post_update_hook(
    repo_root_path: str,
    python_executable: str,
    *,
    hook_module: str = "app.updater.post_update_hook",
) -> None:
    env_python_path = os.environ.get("PYTHONPATH", "")
    backend_path = os.path.join(repo_root_path, "backend")
    if env_python_path:
        python_path = f"{backend_path}{os.pathsep}{env_python_path}"
    else:
        python_path = backend_path
    env = dict(os.environ)
    env["PYTHONPATH"] = python_path
    result = run_argv_capture(
        [python_executable, "-P", "-m", hook_module],
        cwd=repo_root_path,
        env=env,
        encoding="utf-8",
        errors="replace",
        timeout=1200,
    )
    if result.return_code != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or "post-update hook failed without output"
        raise ProcessError(
            "SoAI post-install migration hook failed.",
            details={"detail": detail, "return_code": result.return_code},
            operation="bootstrap.install_deps.post_update_hook",
        )
