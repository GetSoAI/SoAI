"""SoAI - Runtime bootstrap entrypoint after managed dependencies [backend/app/bootstrap_entrypoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import subprocess
import sys
import warnings

from app.cli.startup_flags import handle_information_cli_request
from core.bootstrap.background import contains_background_flag, launch_background
from core.bootstrap.install_arguments import (
    ParsedInstallArguments,
    contains_install_command_or_option,
    parse_install_arguments,
)
from core.bootstrap.install_deps_flags import contains_install_deps_flag
from core.bootstrap.install_deps_windows import (
    WindowsInstallDepsSession,
    begin_windows_install_deps,
)
from core.bootstrap.install_windows import (
    default_windows_install_target,
    install_to_target,
    wait_for_windows_install_to_finish,
)
from core.bootstrap.launch_console import emit
from core.bootstrap.launcher import bootstrap_if_needed
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.bootstrap.stage0_environment import (
    ensure_stage0_soai_python_version,
    is_running_in_soai_venv,
    relaunch_in_venv_or_emit_failure,
    repo_root,
)
from core.bootstrap.windows_managed_venv import ensure_windows_managed_venv
from core.errors.exceptions import SoAIError, SoAITimeoutError
from core.platform.os import is_windows
from core.runtime.opencl_environment import configure_opencl_runtime_environment
from core.system.process_replacement import replace_current_process

__all__ = ("main",)


def _prepare_windows_install_command(repo_root_path: str) -> ParsedInstallArguments | int | None:
    if not is_windows():
        return None
    try:
        if not contains_install_command_or_option(sys.argv[1:]):
            wait_for_windows_install_to_finish(repo_root_path)
            return None
        parsed_args = parse_install_arguments(
            sys.argv[1:],
            default_target=default_windows_install_target(),
            current_directory=os.getcwd(),
        )
        if parsed_args.command == "install":
            install_to_target(repo_root_path, parsed_args)
            return 0
        return parsed_args
    except (
        OSError,
        RuntimeError,
        ValueError,
        SoAITimeoutError,
        subprocess.SubprocessError,
    ) as exception:
        emit(
            "ERROR",
            f"FATAL: Windows install command failed: {type(exception).__name__}: {exception}",
        )
        return 1


def main(
    *,
    runtime_cli_module: str = "app.cli.entrypoint",
    managed_entrypoint_path: str | None = None,
    expected_edition: str = "soai-core",
) -> int:
    information_exit_code = handle_information_cli_request(
        sys.argv[1:],
        program_name=os.path.basename(sys.argv[0]),
    )
    if information_exit_code is not None:
        return information_exit_code
    ensure_stage0_soai_python_version()
    configure_opencl_runtime_environment()
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API\..*",
        category=UserWarning,
        module=r"tika(\..*)?$",
    )
    repo_root_path = repo_root()
    windows_install_args = _prepare_windows_install_command(repo_root_path)
    if isinstance(windows_install_args, int):
        return windows_install_args
    windows_install_deps_session: WindowsInstallDepsSession | None = None
    ensure_runtime_directory_environment(repo_root_path)
    background_mode = contains_background_flag(sys.argv[1:])
    if background_mode:
        emit(
            "INFO",
            "SoAI is starting in background mode. Check soai.log for detailed runtime logs.",
        )
    if not is_running_in_soai_venv(repo_root_path):
        if is_windows():
            try:
                ensure_windows_managed_venv(repo_root_path)
            except (OSError, SoAIError, subprocess.SubprocessError, ValueError) as exception:
                message = " ".join(
                    (
                        "FATAL: Windows managed environment bootstrap failed:",
                        f"{type(exception).__name__}: {exception}",
                    ),
                )
                emit(
                    "ERROR",
                    message,
                )
                return 1
        launched = relaunch_in_venv_or_emit_failure(
            repo_root_path,
            entrypoint_path=(
                managed_entrypoint_path or os.path.join(repo_root_path, "backend", "main.py")
            ),
        )
        return 0 if launched else 1

    if (
        is_windows()
        and windows_install_args is not None
        and windows_install_args.command == "install-deps"
    ):
        try:
            windows_install_deps_session = begin_windows_install_deps(
                repo_root_path,
                windows_install_args,
            )
        except (OSError, RuntimeError, ValueError, SoAITimeoutError) as exception:
            emit("ERROR", f"FATAL: Install dependency preflight failed: {exception}")
            return 1

    try:
        bootstrap_if_needed(repo_root_path)
    except KeyboardInterrupt:
        if windows_install_deps_session is not None:
            windows_install_deps_session.fail(
                "managed-runtime",
                "SoAI managed runtime preparation was interrupted.",
            )
        emit("WARN", "Bootstrap interrupted by user.")
        return 130
    except (
        OSError,
        RuntimeError,
        SoAITimeoutError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exception:
        if windows_install_deps_session is not None:
            windows_install_deps_session.fail(
                "managed-runtime",
                "SoAI managed runtime preparation failed.",
            )
        emit("ERROR", f"FATAL: Bootstrap failed: {type(exception).__name__}: {exception}")
        return 1

    if windows_install_deps_session is not None:
        try:
            windows_install_deps_session.complete(sys.executable)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exception:
            windows_install_deps_session.fail(
                "migration-hook",
                "SoAI V1 post-install migration hook failed.",
            )
            emit("ERROR", f"FATAL: Install dependency completion failed: {exception}")
            return 1

    if contains_install_deps_flag(sys.argv[1:]):
        emit("INFO", "SoAI runtime dependency installation completed.")
        return 0

    if background_mode:
        emit("INFO", "Virtual environment is ready. Launching SoAI in background...")
        return launch_background(
            repo_root_path,
            expected_edition=expected_edition,
            entrypoint_path=managed_entrypoint_path,
        )

    if "SOAI_BOOTSTRAP_DONE" not in os.environ:
        os.environ["SOAI_BOOTSTRAP_DONE"] = "1"
    os.chdir(os.path.join(repo_root_path, "backend"))
    try:
        return replace_current_process(
            [sys.executable, "-m", runtime_cli_module, *sys.argv[1:]],
        )
    except (OSError, ValueError) as exception:
        emit(
            "ERROR",
            f"FATAL: Failed to exec CLI entrypoint: {type(exception).__name__}: {exception}",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
