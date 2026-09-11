"""SoAI - Managed Python dependency bootstrap [backend/core/bootstrap/python_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import time

from core.bootstrap.command_streaming import run_bootstrap_command
from core.bootstrap.files import (
    compute_sha256,
    compute_source_directory_sha256,
    read_text_file,
    write_text_file_atomic,
)
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.pytorch_wheel_urls import resolve_pytorch_direct_wheel_urls
from core.bootstrap.runtime_directories import (
    LOCKS_PATH_ENV,
    ensure_runtime_directory_environment,
)
from core.bootstrap.stage0_environment import is_stage0_offline_mode_enabled
from core.bootstrap.venv_markers import (
    DEPENDENCY_CHECK_MARKER_FILENAME,
    REQUIREMENTS_HASH_FILENAME,
)
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.errors.exceptions import StateError
from core.meta.paths import join_data_abs
from core.system.commands import run_argv_capture

__all__ = (
    "LOCKS_PATH_ENV",
    "PYTHON_DEPS_LOCK_FILENAME",
    "REQUIREMENTS_FILENAME",
    "bootstrap_python_dependencies_if_needed",
    "ensure_pip_ready",
    "runtime_dependencies_need_install",
)

REQUIREMENTS_FILENAME = "requirements.txt"
PYTHON_DEPS_LOCK_FILENAME = "soai.python_deps.lock"
DEPENDENCY_PROBE_IMPORTS: tuple[str, ...] = (
    "fastapi",
    "httpx2",
    "pydantic",
    "playwright",
    "tika",
    "uvicorn",
)


def ensure_pip_ready(python_executable: str) -> None:
    pip_probe = run_argv_capture(
        [python_executable, "-m", "pip", "--version"],
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if pip_probe.return_code == 0:
        return
    raise StateError(
        "pip is missing or broken inside the managed runtime environment. Delete the managed env directory and re-run bootstrap.",
    )


def runtime_dependencies_need_install(source_root: str, *, runtime_path: str) -> bool:
    python_executable = get_venv_python_executable(runtime_path)
    if not os.path.isfile(python_executable):
        raise StateError(
            "The installed managed Python runtime is unavailable for update preparation."
        )
    requirements_path = os.path.join(source_root, REQUIREMENTS_FILENAME)
    requirements_hash = _runtime_dependency_source_hash(
        repo_root_path=source_root,
        requirements_path=requirements_path,
    )
    return _python_dependencies_need_install(
        venv_path=runtime_path,
        python_executable=python_executable,
        requirements_hash=requirements_hash,
    )


def bootstrap_python_dependencies_if_needed(
    repo_root_path: str,
    *,
    python_executable: str | None = None,
    offline_mode: bool | None = None,
) -> bool:
    repo_root = os.path.abspath(repo_root_path)
    venv_path = get_venv_path(repo_root)
    resolved_python = python_executable or get_venv_python_executable(venv_path)
    requirements_path = os.path.join(repo_root, REQUIREMENTS_FILENAME)
    if not os.path.isfile(requirements_path):
        raise FileNotFoundError(
            f"Required file '{requirements_path}' does not exist; cannot bootstrap deps.",
        )
    runtime_directories = ensure_runtime_directory_environment(repo_root)
    lock_path = os.path.join(runtime_directories.locks_path, PYTHON_DEPS_LOCK_FILENAME)
    with acquire_interprocess_lock(lock_path, timeout_sec=1200.0):
        if not os.path.exists(resolved_python):
            raise FileNotFoundError(
                f"SoAI managed environment is missing. Start SoAI via soai.sh or soai.exe to create it. Expected python at '{resolved_python}'.",
            )
        ensure_pip_ready(resolved_python)
        requirements_hash = _runtime_dependency_source_hash(
            repo_root_path=repo_root,
            requirements_path=requirements_path,
        )
        if not _python_dependencies_need_install(
            venv_path=venv_path,
            python_executable=resolved_python,
            requirements_hash=requirements_hash,
        ):
            return False
        resolved_offline_mode = (
            is_stage0_offline_mode_enabled(repo_root)
            if offline_mode is None
            else bool(offline_mode)
        )
        if resolved_offline_mode:
            raise StateError(
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled but required Python dependencies are missing or out of date. Disable SYSTEM.RUNTIME.STAY_OFFLINE and run once online.",
            )
        _install_python_dependencies(
            repo_root_path=repo_root,
            python_executable=resolved_python,
            requirements_path=requirements_path,
        )
        if not _runtime_dependency_probes_pass(resolved_python):
            raise StateError(
                "Managed Python dependency preparation failed its runtime validation. Required modules must be available and pip check must pass before startup."
            )
        _write_dependency_markers(venv_path=venv_path, requirements_hash=requirements_hash)
        return True


def _python_dependencies_need_install(
    *,
    venv_path: str,
    python_executable: str,
    requirements_hash: str,
) -> bool:
    stored_hash = read_text_file(os.path.join(venv_path, REQUIREMENTS_HASH_FILENAME))
    marker_value = read_text_file(os.path.join(venv_path, DEPENDENCY_CHECK_MARKER_FILENAME))
    if stored_hash != requirements_hash or not marker_value:
        return True
    return not _runtime_dependency_probes_pass(python_executable)


def _runtime_dependency_probes_pass(python_executable: str) -> bool:
    import_probe = run_argv_capture(
        [
            python_executable,
            "-c",
            _build_dependency_probe_script(),
        ],
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if import_probe.return_code != 0:
        return False
    pip_check = run_argv_capture(
        [python_executable, "-m", "pip", "check"],
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return pip_check.return_code == 0


def _install_python_dependencies(
    *,
    repo_root_path: str,
    python_executable: str,
    requirements_path: str,
) -> None:
    run_bootstrap_command(
        [
            python_executable,
            "-m",
            "pip",
            "install",
            "--root-user-action=ignore",
            "--upgrade",
            "pip",
            "wheel",
        ],
        log_prefix="pip: ",
        cwd=repo_root_path,
    )
    _install_pytorch_hosted_wheels_if_required(
        repo_root_path=repo_root_path,
        python_executable=python_executable,
        requirements_path=requirements_path,
    )
    run_bootstrap_command(
        [
            python_executable,
            "-m",
            "pip",
            "install",
            "--root-user-action=ignore",
            "--upgrade",
            "--upgrade-strategy",
            "eager",
            "-r",
            requirements_path,
        ],
        log_prefix="pip: ",
        cwd=repo_root_path,
    )


def _install_pytorch_hosted_wheels_if_required(
    *,
    repo_root_path: str,
    python_executable: str,
    requirements_path: str,
) -> None:
    wheel_urls = resolve_pytorch_direct_wheel_urls(requirements_path)
    if not wheel_urls:
        return
    run_bootstrap_command(
        [
            python_executable,
            "-m",
            "pip",
            "install",
            "--root-user-action=ignore",
            "--upgrade",
            "--no-deps",
            *wheel_urls,
        ],
        log_prefix="pip: ",
        cwd=repo_root_path,
    )


def _runtime_dependency_source_hash(*, repo_root_path: str, requirements_path: str) -> str:
    requirements_hash = compute_sha256(requirements_path)
    local_tika_root = join_data_abs(repo_root_path, "vendor", "tika")
    local_tika_hash = "\n".join(
        (
            f"pyproject:{compute_sha256(os.path.join(local_tika_root, 'pyproject.toml'))}",
            f"license:{compute_sha256(os.path.join(local_tika_root, 'LICENSE.txt'))}",
            f"package:{compute_source_directory_sha256(os.path.join(local_tika_root, 'tika'))}",
        ),
    )
    return f"requirements:{requirements_hash}\nlocal-tika:{local_tika_hash}"


def _build_dependency_probe_script() -> str:
    import_names = ", ".join(repr(name) for name in DEPENDENCY_PROBE_IMPORTS)
    return f"import importlib.util, sys\nmissing = [name for name in ({import_names},) if importlib.util.find_spec(name) is None]\nraise SystemExit(1 if missing else 0)\n"


def _write_dependency_markers(*, venv_path: str, requirements_hash: str) -> None:
    write_text_file_atomic(os.path.join(venv_path, REQUIREMENTS_HASH_FILENAME), requirements_hash)
    write_text_file_atomic(
        os.path.join(venv_path, DEPENDENCY_CHECK_MARKER_FILENAME),
        str(_epoch_seconds_float()),
    )


def _epoch_seconds_float() -> float:
    return time.time()
