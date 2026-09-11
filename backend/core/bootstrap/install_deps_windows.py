"""SoAI - Windows install-deps progress session [backend/core/bootstrap/install_deps_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from core.bootstrap.install_arguments import ParsedInstallArguments
from core.bootstrap.install_locks import (
    INSTALL_LOCK_ENV,
    INSTALL_LOCK_TOKEN_ENV,
    acquire_lock_dir,
    lock_dir_has_live_owner,
    read_lock_token,
    release_lock_dir,
)
from core.bootstrap.install_status import InstallStatusOptions, InstallStatusReporter
from core.bootstrap.install_target_windows import reject_running_windows_target
from core.errors.exceptions import ProcessError, StateError
from core.meta.paths import join_data_abs
from core.system.commands import run_argv_capture

__all__ = ("WindowsInstallDepsSession", "begin_windows_install_deps")


@dataclass(slots=True)
class WindowsInstallDepsSession:
    repo_root_path: str
    reporter: InstallStatusReporter
    lock_dir: str
    owns_lock: bool

    def complete(self, python_executable: str) -> None:
        self.emit("managed-runtime", "completed", "SoAI managed runtime is ready.")
        self.emit("runtime-artifacts", "started", "Provisioning SoAI runtime artifacts...")
        self.emit("runtime-artifacts", "completed", "SoAI runtime artifacts are ready.")
        self.emit("migration-hook", "started", "Running SoAI V1 post-install migration hook...")
        _run_post_update_hook(self.repo_root_path, python_executable)
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
        if not self.owns_lock:
            return
        release_lock_dir(self.lock_dir)
        inherited_lock = os.environ.get(INSTALL_LOCK_ENV, "")
        if os.path.abspath(inherited_lock) == os.path.abspath(self.lock_dir):
            os.environ.pop(INSTALL_LOCK_ENV, None)
            os.environ.pop(INSTALL_LOCK_TOKEN_ENV, None)
        self.owns_lock = False


def begin_windows_install_deps(
    repo_root_path: str,
    parsed_args: ParsedInstallArguments,
) -> WindowsInstallDepsSession:
    lock_dir = join_data_abs(repo_root_path, "state", "locks", "soai.install.lock.d")
    owns_lock = False
    if not _inherited_install_lock_is_valid(lock_dir):
        lock_dir = acquire_lock_dir(lock_dir)
        os.environ[INSTALL_LOCK_ENV] = lock_dir
        lock_token = read_lock_token(lock_dir)
        if lock_token is None:
            release_lock_dir(lock_dir)
            raise StateError("SoAI install lock handoff token is missing or invalid.")
        os.environ[INSTALL_LOCK_TOKEN_ENV] = lock_token
        owns_lock = True
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
        owns_lock=owns_lock,
    )
    try:
        session.emit("preflight", "started", "Checking SoAI runtime state...")
        reject_running_windows_target(repo_root_path, expected_edition="soai-core")
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


def _inherited_install_lock_is_valid(lock_dir: str) -> bool:
    inherited_lock = os.environ.get(INSTALL_LOCK_ENV, "")
    if os.path.abspath(inherited_lock) != os.path.abspath(lock_dir):
        return False
    inherited_token = os.environ.get(INSTALL_LOCK_TOKEN_ENV, "")
    lock_token = read_lock_token(lock_dir)
    if not inherited_token or lock_token is None:
        return False
    return secrets.compare_digest(inherited_token, lock_token) and lock_dir_has_live_owner(lock_dir)


def _run_post_update_hook(repo_root_path: str, python_executable: str) -> None:
    env_python_path = os.environ.get("PYTHONPATH", "")
    backend_path = os.path.join(repo_root_path, "backend")
    if env_python_path:
        python_path = f"{backend_path}{os.pathsep}{env_python_path}"
    else:
        python_path = backend_path
    env = dict(os.environ)
    env["PYTHONPATH"] = python_path
    result = run_argv_capture(
        [python_executable, "-m", "app.updater.post_update_hook"],
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
